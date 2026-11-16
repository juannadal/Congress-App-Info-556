"""Pool the top results of every method into a blind judging sheet (eval/judgments.csv).

For each query in eval/queries.csv, the top `depth` passages from BM25, dense, and hybrid
are merged and deduplicated. Within each query the passages are shuffled with a fixed seed
and the sheet doesn't say which method found them, so judging is blind. Label in
eval/judgments.xlsx (written alongside the CSV): `label` 0 = not relevant, 1 = partly relevant,
2 = relevant; `notes` is free text. Saved labels are copied into the CSV on the next pool/score run.

Rerunning is safe: rows already in the sheet (and their labels and notes) are kept, and only
passages not yet in the sheet are added, e.g. after adding queries or pooling deeper.
The rankings are also saved to eval/runs.csv so eval.score scores exactly what was pooled.

Usage (from the project root):
  python -m eval.pool              # top 10 from each method
  python -m eval.pool --depth 20   # deeper pool (scoring still uses the top 10)
"""

import argparse

import pandas as pd

from eval.runs import (JUDGMENTS, JUDGMENTS_XLSX, QUERIES, RUNS, filter_label, load_queries, make_runs, read_csv,
                       sync_from_xlsx, write_csv, write_xlsx, xlsx_is_open)
from retrieval.corpus import load_passages

SHEET_COLUMNS = ["query_id", "group", "query", "filter", "passage_id", "member", "section", "text",
                 "label", "notes", "wikipedia_url"]


def build_rows(pool, queries, passages, seed):
    """Make label-sheet rows for new passages, shuffled so the method stays hidden."""
    # Member, section, and passage text, looked up by passage id.
    info = passages.set_index("passage_id")
    rows = []
    for q in queries.to_dict("records"):
        ids = pool.loc[pool["query_id"] == q["query_id"], "passage_id"]
        # Shuffle inside the question so row order does not reveal which method found the passage.
        for pid in ids.sample(frac=1, random_state=seed).tolist():
            p = info.loc[pid]
            rows.append({"query_id": q["query_id"], "group": q["group"], "query": q["text"],
                         "filter": filter_label(q), "passage_id": pid,
                         "member": f"{p['name']} ({p['party'][0]}-{p['state_code']}, {p['chamber']})",
                         "section": p["section"], "text": p["text"], "label": "", "notes": "",
                         "wikipedia_url": p["wikipedia_url"]})
    return pd.DataFrame(rows, columns=SHEET_COLUMNS)


def main():
    """Run the searches, add any new passages to the label sheet, and save the rankings."""
    parser = argparse.ArgumentParser(description="Pool BM25/dense/hybrid results into a judging sheet.")
    parser.add_argument("--depth", type=int, default=10, help="passages pooled from each method (default 10)")
    parser.add_argument("--seed", type=int, default=556, help="shuffle seed")
    parser.add_argument("--with-rerank", action="store_true",
                        help="also run the re-ranker (kept automatically once runs.csv has it)")
    args = parser.parse_args()
    depth = max(args.depth, 10)  # runs.csv always needs at least the top 10 for scoring

    # Leave the files alone while Excel has the sheet open, then copy any labels typed there.
    if xlsx_is_open():
        raise SystemExit(f"{JUDGMENTS_XLSX.name} is open in Excel; save and close it first.")
    synced = sync_from_xlsx()
    if synced:
        print(f"Copied {synced} edited rows from {JUDGMENTS_XLSX.name} into {JUDGMENTS.name}.")
    queries = load_queries()
    sheet = read_csv(JUDGMENTS) if JUDGMENTS.exists() else pd.DataFrame(columns=SHEET_COLUMNS)

    # Stop if a question's wording changed. Old labels would no longer match the text.
    # A query whose text changed would keep labels judged for the old wording
    current = queries.set_index("query_id")["text"]
    old = sheet.drop_duplicates("query_id").set_index("query_id")["query"]
    changed = [qid for qid in old.index if qid in current.index and old[qid] != current[qid]]
    if changed:
        raise SystemExit(f"query text changed for {changed} since they were pooled. Give the new wording a new "
                         f"query_id, or delete those rows from {JUDGMENTS.name} to re-judge them.")

    # Search again. Include the re-ranker if this run asks for it, or if an older run already has it.
    had_rerank = RUNS.exists() and "rerank" in set(read_csv(RUNS)["method"])
    runs = make_runs(queries, depth=depth, with_rerank=args.with_rerank or had_rerank)
    write_csv(runs, RUNS)
    # Passages to label: the top of each method, once per question.
    pool = runs.loc[runs["rank"] <= args.depth, ["query_id", "passage_id"]].drop_duplicates()

    # Keep rows already on the sheet, labels included. Add only passages that are new.
    seen = set(zip(sheet["query_id"], sheet["passage_id"]))
    new = pool[[(q, p) not in seen for q, p in zip(pool["query_id"], pool["passage_id"])]]
    added = build_rows(new, queries, load_passages(), args.seed)

    # Keep each query's rows together, in queries.csv order; existing rows stay ahead of new ones
    combined = pd.concat([sheet, added], ignore_index=True)
    order = {qid: i for i, qid in enumerate(queries["query_id"])}
    combined["_order"] = combined["query_id"].map(order).fillna(len(order))
    combined = combined.sort_values("_order", kind="stable").drop(columns="_order")
    write_csv(combined, JUDGMENTS)
    write_xlsx(combined)

    # Report how many passages are labeled, how many are still blank, and any question that left the list.
    dropped = sorted(set(sheet["query_id"]) - set(order))
    labeled = combined["label"].str.strip() != ""
    per_query = (combined.assign(labeled=labeled).groupby("query_id", sort=False)
                 .agg(pool=("passage_id", "size"), labeled=("labeled", "sum")))
    print(f"Ran {len(queries)} queries x {runs['method'].nunique()} methods (top {depth}) -> {RUNS.name}")
    print(f"Added {len(added)} passages to {JUDGMENTS.name}; {len(combined)} rows, "
          f"{int(labeled.sum())} labeled, {int((~labeled).sum())} to go.\n")
    print(per_query.to_string())
    if dropped:
        print(f"\nNote: {dropped} are in {JUDGMENTS.name} but not in {QUERIES.name}; their rows were kept.")


if __name__ == "__main__":
    main()
