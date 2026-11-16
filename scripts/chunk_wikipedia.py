"""Split the Wikipedia member articles into paragraph-level passages.

Rules:
  - Sections that aren't prose are dropped (References, External links, See also,
    Notes, Further reading, Electoral history, ...), including their subsections.
  - Each paragraph is a passage. Short paragraphs (< --min-words) are merged
    with the next paragraph in the same section (or the previous one, if last).
  - Runs of list items (e.g. Committee assignments, Caucus memberships) are
    joined into one passage: "Item A; Item B; Item C".
  - Passages longer than --max-words are split at sentence boundaries.
  - Word counts don't guarantee the 256-word-piece input limit of all-MiniLM-L6-v2
    (names, numbers, and punctuation take several pieces), so a final check counts
    word pieces with the model's own tokenizer. Any passage whose text_with_context
    is over --max-tokens is halved at a sentence boundary until it fits, so nothing
    is silently truncated when embedding either column.
  - Passages never cross section boundaries.

Each passage keeps its section path (e.g. "U.S. Senate > Committee assignments")
and the member's metadata, plus a `text_with_context` column that prefixes the
member's name and section, since many passages only say "He" or "She".

Outputs:
  data/passages_{congress}.jsonl
  data/passages_{congress}.csv

Usage:
  python scripts/chunk_wikipedia.py
  python scripts/chunk_wikipedia.py --max-words 150 --min-words 30
"""

import argparse
import re
import sys

import pandas as pd

from fetch_members import DATA_DIR, PROJECT_ROOT

DROP_SECTIONS = {
    "references", "external links", "see also", "notes", "further reading",
    "electoral history", "citations", "sources", "footnotes", "explanatory notes",
    "bibliography", "works cited", "notes and references", "election results",
}

# Captions left behind when the plain-text API strips tables
TABLE_LEFTOVERS = {"source", "sources"}

# The plain-text API renders math as one symbol per line followed by the LaTeX
# source; keep only the LaTeX
MATH_BLOCK = re.compile(r"(?:\n[ \t]*(?:\S{1,3}[ \t]*)?)+\n[ \t]*\{\\displaystyle ([^\n]*)\}[ \t]*(?:\n[ \t]*(?=\n))*")

HEADING = re.compile(r"^(=+)\s*(.*?)\s*=+\s*$")

# Periods in these don't end a sentence
ABBREVIATIONS = re.compile(
    r"\b(?:U\.S|U\.K|U\.N|D\.C|Jr|Sr|Dr|Mr|Mrs|Ms|St|Gen|Lt|Col|Capt|Sgt|Rep|Sen|Gov|"
    r"No|Inc|Co|Corp|Ltd|vs|etc|Ph\.D|M\.D|B\.A|M\.A|J\.D|Mt|Ft|Jan|Feb|Mar|Apr|Aug|"
    r"Sept|Sep|Oct|Nov|Dec|[A-Z])\.$")


def split_sentences(text):
    """Split text into sentences, and keep abbreviations like U.S. together."""
    parts = re.split(r"(?<=[.!?\"”])\s+(?=[A-Z\"“(\[0-9])", text)
    sentences = []
    for part in parts:
        # Re-join splits that happened after an abbreviation like "U.S." or "Jr."
        if sentences and ABBREVIATIONS.search(sentences[-1]):
            sentences[-1] += " " + part
        else:
            sentences.append(part)
    return sentences


def split_long(text, max_words):
    """Split text into pieces of at most max_words, at sentence boundaries."""
    # Already short enough.
    if len(text.split()) <= max_words:
        return [text]
    pieces, current = [], []
    for sentence in split_sentences(text):
        words = sentence.split()
        if len(words) > max_words:  # a single huge "sentence": hard-split by words
            if current:
                pieces.append(" ".join(current))
                current = []
            for i in range(0, len(words), max_words):
                pieces.append(" ".join(words[i:i + max_words]))
            continue
        # Start a new piece when the next sentence would pass the word limit.
        if len(current) + len(words) > max_words:
            pieces.append(" ".join(current))
            current = []
        current.extend(words)
    if current:
        pieces.append(" ".join(current))
    return pieces


def is_list_item(line):
    """Short lines that don't end like a sentence (committee names, caucuses, ...)."""
    stripped = line.strip()
    return len(stripped.split()) <= 12 and not re.search(r"[.!?\"”]$", stripped)


def parse_sections(text):
    """Yield (section_path, [blocks]) where blocks are paragraphs or joined lists."""
    # Text before the first heading counts as the introduction.
    path = ["Introduction"]
    lines = []

    def flush():
        """Turn the saved lines into paragraphs and joined lists."""
        blocks, items = [], []
        # Skip blank lines. Group short list lines, and keep real paragraphs separate.
        for line in lines:
            if not line.strip():
                continue
            if is_list_item(line):
                item = line.strip().rstrip(":;,")
                if item.lower() not in TABLE_LEFTOVERS:
                    items.append(item)
                continue
            if items:
                blocks.append("; ".join(items))
                items = []
            blocks.append(line.strip())
        # Join any list that is still open at the end of the section.
        if items:
            blocks.append("; ".join(items))
        return blocks

    for line in text.split("\n"):
        match = HEADING.match(line)
        if not match:
            lines.append(line)
            continue
        # A new heading closes the section we were reading.
        yield " > ".join(path), flush()
        lines = []
        level = len(match.group(1)) - 1  # "==" is level 1
        # Stay under the parent headings, then add this one.
        path = path[:level - 1] if level > 1 else []
        path.append(match.group(2))
    # Close the last section. Nothing follows it.
    yield " > ".join(path), flush()


def merge_short(blocks, min_words, max_words):
    """Merge blocks shorter than min_words into a neighbor, without exceeding max_words."""
    merged = []
    # Glue a short block onto the previous one when both still fit.
    for block in blocks:
        if merged and len(merged[-1].split()) < min_words \
                and len(merged[-1].split()) + len(block.split()) <= max_words:
            merged[-1] = merged[-1] + " " + block
        else:
            merged.append(block)
    # A short last block joins the previous one if it fits
    if len(merged) > 1 and len(merged[-1].split()) < min_words \
            and len(merged[-2].split()) + len(merged[-1].split()) <= max_words:
        last = merged.pop()
        merged[-1] = merged[-1] + " " + last
    return merged


def context_prefix(article, section):
    """Put the page title and section in front of a passage."""
    return f"{article['wikipedia_title']} - {section}: "


def split_in_half(text):
    """Split text in two at the sentence boundary closest to the middle (by words)."""
    sentences = split_sentences(text)
    if len(sentences) == 1:  # one long sentence: split at the middle word
        words = text.split()
        mid = len(words) // 2
        return [" ".join(words[:mid]), " ".join(words[mid:])]
    # Pick the sentence break closest to the middle.
    lengths = [len(s.split()) for s in sentences]
    total, running, best, best_gap = sum(lengths), 0, 1, None
    for i, n in enumerate(lengths[:-1], start=1):
        running += n
        gap = abs(total - 2 * running)
        if best_gap is None or gap < best_gap:
            best, best_gap = i, gap
    return [" ".join(sentences[:best]), " ".join(sentences[best:])]


def fit_tokens(text, prefix, count_tokens, max_tokens):
    """Halve text at sentence boundaries until prefix + text fits in max_tokens."""
    if count_tokens(prefix + text) <= max_tokens or len(text.split()) < 2:
        return [text]
    return [p for half in split_in_half(text) for p in fit_tokens(half, prefix, count_tokens, max_tokens)]


def chunk_article(article, min_words, max_words, count_tokens, max_tokens):
    """Turn one article into short passages that stay inside one section."""
    passages = []
    # Replace the broken math layout with the formula itself.
    text = MATH_BLOCK.sub(lambda m: " " + m.group(1), article["text"])
    for section, blocks in parse_sections(text):
        # Skip empty sections and sections that are not prose.
        if not blocks or any(part.lower() in DROP_SECTIONS for part in section.split(" > ")):
            continue
        prefix = context_prefix(article, section)
        # Cut long paragraphs, then glue the short ones back together.
        pieces = [p for block in blocks for p in split_long(block, max_words)]
        for merged in merge_short(pieces, min_words, max_words):
            # Cut again if the passage is still too long for the model.
            for text in fit_tokens(merged, prefix, count_tokens, max_tokens):
                passages.append({"section": section, "text": text})
    return passages


def load_token_counter(model_name):
    """Count word pieces the way the embedding model will, including [CLS] and [SEP]."""
    from transformers import AutoTokenizer
    from transformers.utils import logging
    logging.set_verbosity_error()  # silence the "sequence too long" warning we're checking for
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return lambda text: len(tokenizer(text, add_special_tokens=True)["input_ids"])


def main():
    """Split every saved article into passages and write JSONL and CSV files."""
    # Read the size limits and which model's tokenizer to use.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--congress", type=int, default=119)
    parser.add_argument("--max-words", type=int, default=180)
    parser.add_argument("--min-words", type=int, default=40)
    parser.add_argument("--max-tokens", type=int, default=256,
                        help="word-piece limit of the embedding model (default: 256)")
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2",
                        help="model whose tokenizer is used for the --max-tokens check")
    args = parser.parse_args()
    count_tokens = load_token_counter(args.model)

    # Stop if the articles have not been downloaded yet.
    articles_path = DATA_DIR / f"wikipedia_articles_{args.congress}.jsonl"
    if not articles_path.exists():
        sys.exit(f"{articles_path} not found - run scripts/fetch_wikipedia.py first.")
    articles = pd.read_json(articles_path, lines=True, dtype={"bioguide_id": str})

    # Turn each article into passages and copy the member info onto every row.
    rows = []
    for article in articles.to_dict("records"):
        chunks = chunk_article(article, args.min_words, args.max_words, count_tokens, args.max_tokens)
        for i, passage in enumerate(chunks):
            # Put the page title and section in front, so "He" or "She" still names the member.
            with_context = context_prefix(article, passage["section"]) + passage["text"]
            rows.append({
                "passage_id": f"{article['bioguide_id']}-{i:03d}",
                "bioguide_id": article["bioguide_id"],
                "name": article["name"],
                "chamber": article["chamber"],
                "party": article["party"],
                "state_code": article["state_code"],
                "section": passage["section"],
                "passage_index": i,
                "word_count": len(passage["text"].split()),
                "token_count": count_tokens(with_context),
                "text": passage["text"],
                "text_with_context": with_context,
                "wikipedia_url": article["wikipedia_url"],
                "revision_id": article["revision_id"],
            })

    # Save both files and print how the passages came out.
    df = pd.DataFrame(rows)
    jsonl_path = DATA_DIR / f"passages_{args.congress}.jsonl"
    csv_path = DATA_DIR / f"passages_{args.congress}.csv"
    df.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)
    df.to_csv(csv_path, index=False, encoding="utf-8")

    wc = df["word_count"]
    per_article = df.groupby("bioguide_id").size()
    print(f"Chunked {len(articles)} articles into {len(df):,} passages "
          f"(max {args.max_words} words, merge under {args.min_words})")
    print(f"  words per passage: median {int(wc.median())}, "
          f"5th pct {int(wc.quantile(.05))}, 95th pct {int(wc.quantile(.95))}, max {wc.max()}")
    tc = df["token_count"]
    print(f"  word pieces (text_with_context): median {int(tc.median())}, max {tc.max()}, "
          f"over {args.max_tokens}: {(tc > args.max_tokens).sum()}")
    print(f"  passages per article: median {int(per_article.median())}, "
          f"min {per_article.min()}, max {per_article.max()}")
    print(f"  words kept: {wc.sum():,} of {articles['word_count'].sum():,} "
          f"({wc.sum() / articles['word_count'].sum():.0%})")
    print(f"\n  {jsonl_path.relative_to(PROJECT_ROOT)}")
    print(f"  {csv_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
