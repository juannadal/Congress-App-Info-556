"""A language model reads the top passages and puts the best matches first.

LLM re-ranking: a model re-orders the hybrid top 20 for a question (the fourth method).

Hybrid search (BM25 + dense, RRF) returns its top `depth` passages (default 20). The model reads
the question and the numbered passages and returns them ordered from most to least relevant;
the top k of that order is the result. It only re-orders what hybrid found, so it can't
add passages, and it never writes answers.

Every response is cached in eval/rerank_cache.jsonl, keyed by model, question, filter,
and the candidate passage IDs. Rerunning reuses the cache, so an evaluated run is fixed and
each question is paid for once. Delete the cache file to ask again.

The API key is read from the ANTHROPIC_API_KEY environment variable or from ~/.info556/.env
(a line ANTHROPIC_API_KEY=...), outside this project so the key is not in the repo. It is never printed.
"""

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from retrieval.corpus import PROJECT_ROOT
from retrieval.deploy import ENV_FILE, LimitReached, get_secret

# The language model that re-orders the passages.
MODEL = "claude-opus-5-5"
# How many hybrid passages the model reads.
DEPTH = 20
CACHE_PATH = PROJECT_ROOT / "eval" / "rerank_cache.jsonl"

SYSTEM = (
    "You rank passages for a search engine over Wikipedia biographies of members of the 119th U.S. Congress. "
    "Given a question and numbered passages, order all the passages from most to least relevant. A passage is "
    "relevant when it shows that the member it describes fits the question (for example, held the role, has the "
    "background, or took the action asked about). Passages that only share words with the question, or that "
    "describe someone else, are not relevant. Judge only what each passage says."
)

# The answer must be a list of passage numbers, and nothing else.
RANKING_SCHEMA = {
    "type": "object",
    "properties": {"ranking": {"type": "array", "items": {"type": "integer"}}},
    "required": ["ranking"],
    "additionalProperties": False,
}


def load_api_key():
    """ANTHROPIC_API_KEY from the environment, else from ~/.info556/.env. Never printed."""
    key = get_secret("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(f"No re-ranker API key found. Put a line ANTHROPIC_API_KEY=... in {ENV_FILE}.")
    return key


def cache_key(model, query, where, passage_ids):
    """Build a short id for this question, filter, and set of passages."""
    raw = json.dumps([model, query, sorted((where or {}).items()), list(passage_ids)])
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def build_prompt(query, where, candidates):
    """Write the question and the numbered passages for the re-ranker to read."""
    filters = ", ".join(f"{k}={v}" for k, v in (where or {}).items())
    lines = [f"Question: {query}" + (f"  (results are limited to {filters})" if filters else ""), "", "Passages:"]
    for i, r in enumerate(candidates.itertuples(), start=1):
        lines.append(f"[{i}] {r.name} ({r.party}-{r.state_code}, {r.chamber}) | {r.section}\n{r.text}")
    lines += ["", f"Return JSON with \"ranking\": the passage numbers 1-{len(candidates)}, each exactly once, "
                  "most relevant first."]
    return "\n".join(lines)


# Use the model's order, then add any passages it skipped, in the old order.
def clean_order(ranking, n):
    """Keep valid, first-seen numbers; append any the model left out in hybrid order."""
    seen, order = set(), []
    for x in ranking:
        if isinstance(x, int) and 1 <= x <= n and x not in seen:
            seen.add(x)
            order.append(x)
    return order + [x for x in range(1, n + 1) if x not in seen]


class LLMReranker:
    """Re-orders a hybrid result list with a language model."""

    def __init__(self, hybrid, model=MODEL, depth=DEPTH, cache_path=CACHE_PATH, client=None):
        """Remember the hybrid index and load any saved rankings."""
        self.hybrid = hybrid
        self.passages = hybrid.passages
        self.model = model
        self.depth = depth
        self.cache_path = Path(cache_path)
        self._client = client
        self.cache = {}
        # Read earlier answers so the same question is not paid for twice.
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self.cache[entry["key"]] = entry

    @property
    def client(self):
        """Open the connection to the re-ranker the first time it is needed."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=load_api_key())
        return self._client

    def ask(self, query, where, candidates):
        """Send the question and passages to the re-ranker and read back its order."""
        import anthropic
        # Ask for every passage number, best match first.
        prompt = build_prompt(query, where, candidates)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": RANKING_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if this model declines, the API retries on a fallback model
        )
        # Stop if the model refuses. Otherwise read the list of numbers.
        if response.stop_reason == "refusal":
            raise RuntimeError(f"The re-ranker declined to rank {query!r}")
        text = next(b.text for b in response.content if b.type == "text")
        ranking = json.loads(text)["ranking"]
        return ranking, response.model, response.usage

    def search(self, query, k=10, where=None, allow_call=None):
        """Top-k after re-ranking, as a DataFrame with rank, score, and the hybrid rank of each passage.

        `allow_call`, if given, is asked before each new (uncached) re-ranker call; returning False raises
        LimitReached. The public site uses it to cap paid calls.
        """
        # Start from hybrid's short list. The re-ranker cannot add passages.
        candidates = self.hybrid.search(query, k=self.depth, where=where)
        if candidates.empty:
            return candidates
        # Reuse a saved order when this exact list was ranked before.
        key = cache_key(self.model, query, where, candidates["passage_id"])
        if key not in self.cache:
            # Check the paid-call cap, then ask the model and save its answer.
            if allow_call is not None and not allow_call():
                raise LimitReached("re-ranker limit reached")
            ranking, served_by, usage = self.ask(query, where, candidates)
            entry = {"key": key, "model": self.model, "served_by": served_by, "query": query, "where": where or {},
                     "passage_ids": list(candidates["passage_id"]), "ranking": ranking,
                     "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                     "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            self.cache[key] = entry
        # Put the passages in the model's order and keep the top ones.
        order = clean_order(self.cache[key]["ranking"], len(candidates))
        results = candidates.iloc[[i - 1 for i in order]].head(k).copy()
        # Remember where hybrid had placed each one. The new score is 1, 1/2, 1/3, and so on.
        results.insert(2, "hybrid_rank", results.pop("rank").to_numpy())
        results["score"] = 1.0 / pd.Series(range(1, len(results) + 1), index=results.index)
        results.insert(0, "rank", range(1, len(results) + 1))
        return results.reset_index(drop=True)
