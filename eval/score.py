"""Score how well each method ranks passages a person has labeled.
nDCG@10 scores the top 10 results. A relevant passage near the top counts more than one near the bottom.
Recall@10 is the share of relevant passages that appear in the top 10.
MRR is 1 divided by the rank of the first relevant passage.
The pool for a question is every passage labeled for it.

Score each method on the judged queries: nDCG@10, Recall@10, MRR, and significance tests.

Reads eval/runs.csv (the rankings eval.pool judged) and the labels in eval/judgments.csv.

Metrics, per query, on each method's top k (default 10):
  nDCG@k     graded gain = the label (0/1/2), discount 1/log2(rank + 1); the ideal ranking is
             built from every judged passage for the query, whichever method found it
  Recall@k   relevant passages in the top k / all relevant passages in the judged pool
  MRR        1 / rank of the first relevant passage in the top k (0 if none)
"Relevant" means label >= 1 for Recall and MRR (--min-relevant 2 counts only fully relevant).
Queries with no relevant passage in the pool are left out of the averages and listed.

Unjudged passages: by default, a query is only scored once every passage in every method's
top k has a label; partly judged queries are listed and skipped. --allow-unjudged scores them
anyway, counting unjudged passages as not relevant, and reports how many there were.

A significance test asks if a score gap is bigger than chance.
Holm adjustment raises the bar when many pairs are tested.
Cohen's d compares the size of the gap with how much the questions differ.

Significance: for each pair of methods, metric, and query group, a two-sided paired
randomization (sign-flip) test and a Wilcoxon signed-rank test on the per-query differences,
with the mean difference and Cohen's d_z (mean difference / SD of differences) as effect
sizes. p_rand_holm is the randomization p-value Holm-adjusted over the three method pairs.

Usage (from the project root):
  python -m eval.score
  python -m eval.score --allow-unjudged --min-relevant 2
"""

import argparse
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from eval.runs import GROUPS, JUDGMENTS, METHODS, RESULTS_DIR, RUNS, load_judgments, load_queries, write_csv

METRICS = ("ndcg", "recall", "mrr")


def dcg(gains):
    """Add up labels down a ranked list. A high label near the top adds more."""
    gains = np.asarray(gains, dtype=float)
    return float((gains / np.log2(np.arange(2, len(gains) + 2))).sum())


# Score one method's top passages for a single question.
def score_query(top, labels, k, min_relevant):
    """Metrics for one ranked list. `labels` maps passage_id -> label for every judged passage."""
    gains = [labels.get(pid, 0) for pid in top]
    relevant = {pid for pid, lab in labels.items() if lab >= min_relevant}
    ideal = dcg(sorted(labels.values(), reverse=True)[:k])
    first = next((i for i, pid in enumerate(top, 1) if pid in relevant), None)
    return {"ndcg": dcg(gains) / ideal,
            "recall": len(relevant.intersection(top)) / len(relevant),
            "mrr": 1 / first if first else 0.0,
            "unjudged": sum(pid not in labels for pid in top)}


# Ask if a gap this large still shows up when each question's winner is flipped at random.
def randomization_test(diffs, n_resamples=10000, seed=556):
    """Two-sided paired sign-flip test of mean(diffs) == 0."""
    diffs = np.asarray(diffs, dtype=float)
    observed = abs(diffs.mean())
    signs = np.random.default_rng(seed).choice([-1.0, 1.0], size=(n_resamples, len(diffs)))
    extreme = (np.abs((signs * diffs).mean(axis=1)) >= observed - 1e-12).sum()
    return (extreme + 1) / (n_resamples + 1)


def holm(pvalues):
    """Raise the bar when many pairs are tested, so one lucky gap is less likely to count."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    for i, idx in enumerate(order):
        running = max(running, (len(p) - i) * p[idx])
        adjusted[idx] = min(running, 1.0)
    return adjusted


def significance(per_query, methods):
    """Compare method pairs and record whether each score gap is larger than chance."""
    rows = []
    # All questions together, then keyword, conceptual, and filtered on their own.
    scopes = [("all", per_query)] + [(g, per_query[per_query["group"] == g]) for g in GROUPS]
    for scope, df in scopes:
        for metric in METRICS:
            wide = df.pivot(index="query_id", columns="method", values=metric)
            block = []
            # Gap on each question, then a rank test and a sign-flip test.
            for a, b in combinations(methods, 2):
                pair = wide[[a, b]].dropna() if {a, b} <= set(wide.columns) else pd.DataFrame()
                if len(pair) < 2:
                    continue
                diffs = (pair[b] - pair[a]).to_numpy()
                sd = diffs.std(ddof=1)
                p_wil = 1.0 if not diffs.any() else wilcoxon(diffs).pvalue
                block.append({"scope": scope, "metric": metric, "method_a": a, "method_b": b, "n": len(pair),
                              "mean_a": pair[a].mean(), "mean_b": pair[b].mean(), "mean_diff_b_minus_a": diffs.mean(),
                              "cohens_dz": diffs.mean() / sd if sd > 0 else np.nan,
                              "p_wilcoxon": p_wil, "p_randomization": randomization_test(diffs)})
            # Inside this score and question group, raise the bar for the number of pairs tested.
            if block:
                for row, adj in zip(block, holm([r["p_randomization"] for r in block])):
                    row["p_rand_holm"] = adj
                rows.extend(block)
    return pd.DataFrame(rows)


def main():
    """Score the saved rankings against the labels and write the result tables."""
    parser = argparse.ArgumentParser(description="Score BM25/dense/hybrid against the relevance labels.")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--min-relevant", type=int, default=1, choices=[1, 2],
                        help="lowest label that counts as relevant for Recall and MRR (default 1)")
    parser.add_argument("--allow-unjudged", action="store_true",
                        help="score partly judged queries, counting unjudged passages as not relevant")
    args = parser.parse_args()

    # Stop if the rankings or the label sheet have not been built yet.
    for path, cmd in [(RUNS, "python -m eval.pool"), (JUDGMENTS, "python -m eval.pool")]:
        if not path.exists():
            raise SystemExit(f"{path.name} not found; run: {cmd}")
    queries = load_queries().set_index("query_id")
    runs = pd.read_csv(RUNS, dtype={"query_id": str, "passage_id": str})
    sheet = load_judgments()
    # Every test question must already have a saved ranking.
    missing = sorted(set(queries.index) - set(runs["query_id"]))
    if missing:
        raise SystemExit(f"{missing} are in queries.csv but not in runs.csv; run: python -m eval.pool")
    # A tight filter can leave fewer than k hits. Scoring still runs.
    if runs.groupby(["query_id", "method"])["rank"].max().min() < args.k and len(runs):
        print(f"Note: some runs have fewer than {args.k} results (e.g. a filter with few matches).\n")

    methods = [m for m in METHODS if m in set(runs["method"])]
    # Keep judged rows only. A blank label means nobody has marked that passage yet.
    judged = sheet.dropna(subset=["label"])
    labels = {qid: dict(zip(g["passage_id"], g["label"].astype(int))) for qid, g in judged.groupby("query_id")}

    rows, skipped_partial, no_relevant = [], [], []
    for qid, q in queries.iterrows():
        # Each method's top passage ids for this question.
        tops = {m: runs.loc[(runs["query_id"] == qid) & (runs["method"] == m)]
                .sort_values("rank")["passage_id"].head(args.k).tolist() for m in methods}
        qlabels = labels.get(qid, {})
        unjudged = {pid for top in tops.values() for pid in top} - set(qlabels)
        # Wait until those top hits are labeled, unless blanks may count as not relevant.
        if unjudged and not args.allow_unjudged:
            skipped_partial.append(f"{qid} ({len(unjudged)} unjudged)")
            continue
        # Leave out a question when the pool has nothing relevant to find.
        if not any(lab >= args.min_relevant for lab in qlabels.values()):
            no_relevant.append(qid)
            continue
        for m in methods:
            rows.append({"query_id": qid, "group": q["group"], "query": q["text"], "method": m,
                         **score_query(tops[m], qlabels, args.k, args.min_relevant)})

    # Name the questions that were not scored.
    if skipped_partial:
        print(f"Skipped {len(skipped_partial)} partly judged queries (finish labeling or use --allow-unjudged): "
              + ", ".join(skipped_partial) + "\n")
    if no_relevant:
        print(f"Left out {len(no_relevant)} queries with no relevant passage in the pool: {', '.join(no_relevant)}\n")
    if not rows:
        raise SystemExit("No queries to score yet.")

    per_query = pd.DataFrame(rows)
    # When blanks are allowed, show how many were counted as not relevant.
    if per_query["unjudged"].any():
        counts = per_query[per_query["unjudged"] > 0].pivot(index="query_id", columns="method", values="unjudged")
        print(f"Unjudged passages in the top {args.k}, counted as not relevant:\n"
              f"{counts.fillna(0).astype(int).to_string()}\n")

    # Average each score over all questions, then again inside each question type.
    summary = pd.concat([per_query.assign(scope="all"), per_query.assign(scope=per_query["group"])])
    summary = (summary.groupby(["scope", "method"])
               .agg(n=("query_id", "size"), ndcg=("ndcg", "mean"), recall=("recall", "mean"),
                    mrr=("mrr", "mean"), unjudged=("unjudged", "sum")).reset_index())
    scope_order = {s: i for i, s in enumerate(("all", *GROUPS))}
    summary = summary.sort_values(["scope", "method"], key=lambda c: c.map(scope_order) if c.name == "scope"
                                  else c.map({m: i for i, m in enumerate(methods)}))
    # Test whether each pair's gap is larger than chance.
    sig = significance(per_query, methods)

    # Save the three tables the Results page reads.
    RESULTS_DIR.mkdir(exist_ok=True)
    write_csv(per_query, RESULTS_DIR / "per_query.csv")
    write_csv(summary, RESULTS_DIR / "summary.csv")
    write_csv(sig, RESULTS_DIR / "significance.csv")

    # Print the averages and the pair tests.
    k = args.k
    print(summary.rename(columns={"ndcg": f"nDCG@{k}", "recall": f"Recall@{k}", "mrr": "MRR"})
          .to_string(index=False, float_format="{:.3f}".format))
    if len(sig):
        cols = ["scope", "metric", "method_a", "method_b", "n", "mean_diff_b_minus_a", "cohens_dz",
                "p_wilcoxon", "p_randomization", "p_rand_holm"]
        print("\nPaired tests (difference = method_b - method_a):")
        print(sig[cols].to_string(index=False, float_format="{:.3f}".format))
    print(f"\nWrote per_query.csv, summary.csv, significance.csv to {RESULTS_DIR}")


if __name__ == "__main__":
    main()
