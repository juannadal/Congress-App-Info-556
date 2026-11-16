"""Turn logged searches (eval/query_log.csv) into test queries (eval/queries.csv), never adding one twice.

The log lists every search, so the same question run with BM25, dense, and hybrid appears
three times; here each distinct question (text + filters) is listed once, newest first, and
numbered. Questions already in queries.csv are marked and never added twice.

New rows get the next free ID for their group (k21, c21, f11, ...) and "from log" in notes.
A question with a filter goes in the "filtered" group unless --group says otherwise; one
without a filter needs --group.

Usage (from the project root):
  python -m eval.promote                                # list logged questions
  python -m eval.promote --pick 3 5 --group conceptual  # add questions 3 and 5 from the list
  python -m eval.promote --last 2 --group keyword       # add the 2 newest questions not yet added
"""

import argparse

import pandas as pd

from eval.runs import GROUPS, QUERIES, load_queries, read_csv, write_csv
from retrieval.querylog import LOG_PATH

KEY = ["query", "chamber", "party", "state"]
PREFIX = {"keyword": "k", "conceptual": "c", "filtered": "f"}


def logged_questions(queries):
    """List each different logged search once, newest first, and mark ones already saved as test questions."""
    log = read_csv(LOG_PATH)
    log["query"] = log["query"].str.strip()
    log["state"] = log["state"].str.upper()
    # Newest search of each question comes first. Count how often it was asked and which methods ran.
    distinct = (log.iloc[::-1].groupby(KEY, sort=False)
                .agg(last_asked=("timestamp", "first"), times=("timestamp", "size"),
                     methods=("method", lambda m: ",".join(sorted(set(m))))).reset_index())
    # Mark questions already in the test file, and number the list from 1.
    existing = set(zip(queries["text"].str.lower(), queries["chamber"], queries["party"], queries["state"]))
    distinct["in_queries"] = [(q.lower(), c, p, s) in existing for q, c, p, s in distinct[KEY].itertuples(index=False)]
    distinct.index = range(1, len(distinct) + 1)
    return distinct


def next_ids(queries, group, n):
    """Ids that follow the highest number already used in that group, such as k21 after k20."""
    prefix = PREFIX[group]
    used = queries["query_id"][queries["query_id"].str.fullmatch(fr"{prefix}\d+")].str[1:].astype(int)
    start = (used.max() if len(used) else 0) + 1
    return [f"{prefix}{i:02d}" for i in range(start, start + n)]


def append_queries(queries, chosen, groups, notes):
    """Append questions (a DataFrame with KEY columns) to queries.csv with the next IDs; return the new rows."""
    rows = []
    for group in GROUPS:
        part = chosen[groups == group]
        for qid, q in zip(next_ids(queries, group, len(part)), part.itertuples()):
            rows.append({"query_id": qid, "group": group, "text": q.query, "chamber": q.chamber,
                         "party": q.party, "state": q.state, "notes": notes})
    current = read_csv(QUERIES)
    write_csv(pd.concat([current, pd.DataFrame(rows)], ignore_index=True), QUERIES)
    return rows


def add_query(text, group, chamber="", party="", state="", notes="from app"):
    """Add one question to queries.csv (used by the Streamlit app). Returns (query_id, added);
    if the same text and filters are already there, the existing query_id and False."""
    queries = load_queries()
    text, state = text.strip(), state.upper()
    same = queries[(queries["text"].str.lower() == text.lower()) & (queries["chamber"] == chamber)
                   & (queries["party"] == party) & (queries["state"] == state)]
    if len(same):
        return same["query_id"].iloc[0], False
    chosen = pd.DataFrame([{"query": text, "chamber": chamber, "party": party, "state": state}])
    row, = append_queries(queries, chosen, pd.Series([group]), notes)
    return row["query_id"], True


def main():
    """Print logged searches, or add the ones you name to the test-question file."""
    parser = argparse.ArgumentParser(description="Add logged searches to eval/queries.csv.")
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument("--pick", type=int, nargs="+", metavar="N", help="numbers from the list")
    pick.add_argument("--last", type=int, metavar="N", help="the N newest questions not in queries.csv yet")
    parser.add_argument("--group", choices=GROUPS)
    args = parser.parse_args()

    # The log grows when someone searches from the command line or the app.
    if not LOG_PATH.exists():
        raise SystemExit(f"No searches logged yet ({LOG_PATH}). Search in the app first.")
    queries = load_queries()
    questions = logged_questions(queries)

    # No numbers were chosen, so just print the list.
    if args.pick is None and args.last is None:
        shown = questions.assign(added=questions["in_queries"].map({True: "yes", False: ""}))
        print(shown[["last_asked", "times", "methods", *KEY, "added"]].to_string())
        print(f"\nAdd with: python -m eval.promote --pick N [N ...] --group keyword|conceptual|filtered")
        return

    # --pick uses list numbers. --last takes the newest questions that are not test questions yet.
    if args.pick is not None:
        bad = [n for n in args.pick if n not in questions.index]
        if bad:
            raise SystemExit(f"no logged question numbered {bad}; run python -m eval.promote to see the list")
        chosen = questions.loc[args.pick]
    else:
        chosen = questions[~questions["in_queries"]].head(args.last)
    # Skip a picked question that is already a test question.
    skipped = chosen[chosen["in_queries"]]
    chosen = chosen[~chosen["in_queries"]].drop_duplicates(KEY)
    if len(skipped):
        print(f"Already in {QUERIES.name}, skipped: {', '.join(skipped['query'])}")
    if chosen.empty:
        print("Nothing to add.")
        return

    # Without --group, a filtered question goes under filtered, and one with no filter is refused.
    has_filter = (chosen[["chamber", "party", "state"]] != "").any(axis=1)
    if args.group:
        groups = pd.Series(args.group, index=chosen.index)
    else:
        groups = has_filter.map({True: "filtered", False: None})
    if groups.isna().any():
        raise SystemExit(f"--group is needed for questions without a filter: {', '.join(chosen.loc[groups.isna(), 'query'])}")

    # Write the new rows and print each id.
    for r in append_queries(queries, chosen, groups, notes="from log"):
        filters = ", ".join(f"{c}={r[c]}" for c in ("chamber", "party", "state") if r[c])
        print(f"Added {r['query_id']} ({r['group']}): {r['text']}" + (f"  [{filters}]" if filters else ""))


if __name__ == "__main__":
    main()
