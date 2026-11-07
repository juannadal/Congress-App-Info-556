"""AI overview: a short answer written by Grok (xAI API) from the top search results, with numbered
citations that link to each member's Wikipedia article.

This is a display layer only. It reads the passages a search already returned (the re-ranker's
order when that ran, otherwise hybrid) and never changes any ranking, so the evaluation in eval/ is
unaffected. Grok is told to use only those passages and to cite each claim as [n].

Settings (environment variables, or ~/.info556/.env on the Mac; see retrieval/deploy.py):
  XAI_API_KEY        required; without it the overview is turned off
  XAI_MODEL          default "grok-4.7"
  OVERVIEW_ENABLED   "0" turns the overview off everywhere (kill switch for the public site)

Each new overview counts against the public site's paid-call limit (retrieval.deploy.allow_paid_call,
shared with the re-ranker; no limit when running locally). Answers are cached in
cache/overview_cache.jsonl by model, question, filter, and source passages, so repeats are free.
"""

import datetime
import hashlib
import json
import re
import time

import requests

from retrieval.corpus import PROJECT_ROOT
from retrieval.deploy import LIMIT_MESSAGE, allow_paid_call, get_secret

API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4.7"
MAX_SOURCES = 8          # passages sent to Grok
MAX_PER_MEMBER = 2       # so one member's article can't fill every slot
MAX_OUTPUT_TOKENS = 600
TIMEOUT = (10, 45)       # connect, read (seconds of silence before giving up)
DEADLINE = 90            # most seconds one overview may take in total
CACHE_PATH = PROJECT_ROOT / "cache" / "overview_cache.jsonl"

SYSTEM = (
    "You write a short overview that answers a search question about members of the 119th U.S. Congress, "
    "using only the numbered Wikipedia passages provided. Rules:\n"
    "- Answer in 2 to 5 sentences, or a short bulleted list when several members fit. Name the members.\n"
    "- After every claim, cite the passage(s) it comes from as [n], e.g. [2] or [1][4].\n"
    "- Use only what the passages say. Do not add facts from memory, even if you know them.\n"
    "- If the passages don't answer the question, say so in one sentence.\n"
    "- Plain text and Markdown only; no headings, no preamble, no closing remarks."
)


class OverviewError(Exception):
    """Shown to the user as a short note; the search results still display."""


def model():
    """The model name for the overview, or the default."""
    return get_secret("XAI_MODEL") or DEFAULT_MODEL


def status():
    """(available, reason). The search page disables the overview switch when this is not available."""
    if (get_secret("OVERVIEW_ENABLED") or "1").strip().lower() in ("0", "false", "no", "off"):
        return False, "The AI overview is turned off on this site."
    if not get_secret("XAI_API_KEY"):
        return False, "No xAI API key is set, so the AI overview is off."
    return True, ""


# --- building the request ---

def select_sources(hits, n=MAX_SOURCES, per_member=MAX_PER_MEMBER):
    """The first n passages of a ranking, at most `per_member` from any one member."""
    if hits is None or hits.empty:
        return hits
    keep = hits.groupby("bioguide_id", sort=False).cumcount() < per_member
    return hits[keep].head(n).reset_index(drop=True)


def build_messages(query, where, sources):
    """Turn the question and the chosen passages into the note sent to the model."""
    filters = ", ".join(f"{k.replace('_code', '')}={v}" for k, v in (where or {}).items())
    lines = [f"Question: {query}" + (f"  (search limited to {filters})" if filters else ""), "", "Passages:"]
    for i, r in enumerate(sources.itertuples(), start=1):
        lines.append(f"[{i}] {r.name} ({r.party[0]}-{r.state_code}, {r.chamber}) | {r.section}\n{r.text}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def cache_key(model_name, query, where, passage_ids):
    """Build a short id so the same question and passages can reuse a saved overview."""
    raw = json.dumps([model_name, query.strip().lower(), sorted((where or {}).items()), list(passage_ids)])
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _load_cache(path=CACHE_PATH):
    """Read saved overviews from disk."""
    cache = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                cache[entry["key"]] = entry
    return cache


# Saved overviews. Loaded the first time one is needed.
_cache = None


def cached(query, where, sources):
    """The cached overview text for these sources, or None."""
    global _cache
    if _cache is None:
        _cache = _load_cache()
    entry = _cache.get(cache_key(model(), query, where, sources["passage_id"]))
    return entry["text"] if entry else None


def _save(query, where, sources, text, model_name):
    """Save this overview so the next identical question is free."""
    entry = {"key": cache_key(model_name, query, where, sources["passage_id"]), "model": model_name,
             "query": query, "where": where or {}, "passage_ids": list(sources["passage_id"]), "text": text,
             "time": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
    # Remember it in memory, then append the same copy to the cache file.
    _cache[entry["key"]] = entry
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # read-only disk: keep the in-memory copy


# --- calling Grok ---

# Ask the model and hand back the answer in small pieces as they arrive.
def _stream_grok(messages, model_name, key):
    """Yield text pieces from xAI's streaming chat completions endpoint (server-sent events)."""
    # Request a streamed answer. Turn a timeout or a dead connection into a short note.
    body = {"model": model_name, "messages": messages, "stream": True, "max_tokens": MAX_OUTPUT_TOKENS}
    try:
        resp = requests.post(API_URL, json=body, stream=True, timeout=TIMEOUT,
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    except requests.Timeout:
        raise OverviewError(f"Grok didn't respond within {TIMEOUT[1]} seconds, so the overview was skipped.") from None
    except requests.RequestException as e:
        raise OverviewError(f"Couldn't reach the xAI API ({type(e).__name__}).") from None
    # A failed call becomes a note the user can read. Hide the key if it shows up in the error.
    if resp.status_code != 200:
        detail = resp.text[:200].replace(key, "***")
        if resp.status_code == 429:
            raise OverviewError("The xAI API is rate limiting requests; try again in a minute.")
        raise OverviewError(f"The xAI API returned an error ({resp.status_code}): {detail}")
    resp.encoding = "utf-8"  # text/event-stream has no charset, and requests would fall back to Latin-1
    # Read until the answer ends or the connection drops.
    try:
        with resp:
            yield from _read_events(resp)
    except requests.Timeout:
        raise OverviewError(f"Grok went quiet for {TIMEOUT[1]} seconds, so the overview was skipped.") from None
    except requests.RequestException as e:  # dropped connection mid-stream
        raise OverviewError(f"The connection to the xAI API broke off ({type(e).__name__}).") from None


# Read the streamed answer piece by piece, and stop if it runs too long.
def _read_events(resp):
    """Text pieces from a server-sent-events response, until [DONE] or the deadline."""
    # Stop if the answer takes too long, or when the stream says it is done.
    start = time.monotonic()
    for raw in resp.iter_lines(decode_unicode=True):
        if time.monotonic() - start > DEADLINE:
            raise OverviewError(f"Grok took longer than {DEADLINE} seconds, so the overview was skipped.")
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[5:].strip()
        if data == "[DONE]":
            break
        # Each event may carry a small piece of the answer.
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices") or []:
            piece = (choice.get("delta") or {}).get("content")
            if piece:
                yield piece


def stream_overview(query, where, sources):
    """Yield the overview text in pieces (one piece when cached). Raises OverviewError on any failure,
    including when the paid-call limit is reached."""
    # There is nothing to summarize.
    if sources is None or sources.empty:
        raise OverviewError("No passages to summarize.")
    # A saved answer is free and comes back in one piece.
    text = cached(query, where, sources)
    if text is not None:
        yield text
        return
    # The feature must be on, and this call must still be within the cap.
    ok, reason = status()
    if not ok:
        raise OverviewError(reason)
    if not allow_paid_call("overview"):
        raise OverviewError(LIMIT_MESSAGE)
    # Stream a new answer, then save it. An empty answer is an error.
    model_name = model()
    parts = []
    for piece in _stream_grok(build_messages(query, where, sources), model_name, get_secret("XAI_API_KEY")):
        parts.append(piece)
        yield piece
    text = "".join(parts).strip()
    if not text:
        raise OverviewError("Grok returned an empty answer.")
    _save(query, where, sources, text, model_name)


# --- display helpers ---

# Matches a citation like [2] or [1, 3] in the overview.
CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def link_citations(text, sources):
    """Turn [2] or [1, 3] into links to each member's Wikipedia article; drop numbers out of range."""
    # Turn one citation into links. Drop a number that is not in the source list.
    def repl(m):
        links = []
        for num in (int(x) for x in m.group(1).split(",")):
            if 1 <= num <= len(sources):
                r = sources.iloc[num - 1]
                title = f"{r['name']}: {r.section}".replace('"', "'")
                links.append(f"[\\[{num}\\]]({r.wikipedia_url} \"{title}\")")
        return "".join(links)
    return CITATION.sub(repl, text)


def sources_markdown(sources):
    """A numbered list of the source passages, each linked to that member's Wikipedia page."""
    return "\n".join(f"{i}. [{r.name}]({r.wikipedia_url}) ({r.party[0]}-{r.state_code}, {r.chamber}) · {r.section}"
                     for i, r in enumerate(sources.itertuples(), start=1))
