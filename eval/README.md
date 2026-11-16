# Evaluation

The test questions, relevance labels, and scores used to compare the four search methods (BM25, dense, hybrid,
re-ranker). Everything here can be rerun from the project root with `python -m eval.<module>`.

## Workflow

```
queries.csv ──► python -m eval.pool ──► runs.csv + judgments.csv ──► label (app or Excel) ──► python -m eval.score ──► results/
 50 questions      each method's top 10,    rankings + blind pool        0 / 1 / 2               nDCG@10, Recall@10,
                   merged and shuffled                                                           MRR, significance
```

1. **Questions** are in `queries.csv`: 20 keyword, 20 conceptual, and 10 filtered by chamber, party, or state.
2. **Pooling** (`python -m eval.pool`) runs every method on every question, saves each method's ranking to
   `runs.csv`, and adds every passage that appears in any method's top 10 to `judgments.csv`. The passages are
   shuffled and the sheet doesn't say which method found them, so labeling is blind.
3. **Labeling:** each pooled passage gets 0 (not relevant), 1 (partly relevant), or 2 (relevant), following
   `LABELING_GUIDE.md`. Labels can be entered on the app's **Label passages** page or in `judgments.xlsx`.
4. **Scoring** (`python -m eval.score`) computes the metrics from `runs.csv` and `judgments.csv` and writes
   `results/`. The app's **Results** page displays them.

## Files

### Code

| File | What it does |
|---|---|
| `runs.py` | Shared helpers: loads and checks `queries.csv`, runs every method over the questions, and reads and writes the label sheet (CSV and Excel) |
| `pool.py` | Builds the pool: `runs.csv` and new rows in `judgments.csv` (`python -m eval.pool`) |
| `score.py` | Computes nDCG@10, Recall@10, MRR, and significance tests, and writes `results/` (`python -m eval.score`) |
| `promote.py` | Turns searches logged by the app (`query_log.csv`) into new test questions (`python -m eval.promote`) |

### Data used for the reported results

| File | Rows | What it is |
|---|---|---|
| `queries.csv` | 50 | **The final test questions.** Columns: `query_id` (`k01`–`k20` keyword, `c01`–`c20` conceptual, `f01`–`f10` filtered), `group`, `text`, the optional `chamber` / `party` / `state` filter, `wave` (labeling order), `notes` (approval and any rewording) |
| `runs.csv` | 2,000 | Each method's top 10 for each question (50 questions × 4 methods × 10). Columns: `query_id`, `method`, `rank`, `passage_id`, `score`. Scoring uses these saved rankings, so the results don't change if the code or indexes change later. |
| `judgments.csv` | 1,121 | **The relevance labels.** One row per (question, passage) in the pool: 1,020 passages from the BM25, dense, and hybrid pool, plus 101 passages that only the re-ranker brought into its top 10. Labels: 481 relevant (2), 242 partly relevant (1), 398 not relevant (0). See the columns below. |
| `rerank_cache.jsonl` | 62 | Every re-ranker answer: model, question, filter, the 20 candidate passage IDs, the returned order, and token counts. The 50 test questions are included, so the re-ranker results can be reproduced without an API key. A few rows come from searches in the app. |
| `results/summary.csv` | 16 | Mean nDCG@10, Recall@10, and MRR per method, overall and per question group |
| `results/per_query.csv` | 200 | The same metrics for every question and method |
| `results/significance.csv` | 72 | Paired randomization and Wilcoxon tests for each pair of methods, with Holm-adjusted p-values and effect sizes (Cohen's d_z) |

`judgments.csv` columns:

| Column | Meaning |
|---|---|
| `query_id`, `group`, `query`, `filter` | The question |
| `passage_id`, `member`, `section`, `text`, `wikipedia_url` | The passage being judged (`passage_id` matches `data/passages_119.jsonl`) |
| `label` | **The final label** (0, 1, or 2), set by the author. This is the column scoring uses. |
| `notes` | The author's notes |
| `ai_label`, `ai_note` | The AI-drafted label and its reason (blank for the 101 re-ranker passages, which the author labeled from scratch) |
| `reviewed` | `yes` once the author has checked the passage |

### Labeling records

These document how the labels were made. Scoring doesn't read them.

| File | What it is |
|---|---|
| `LABELING_GUIDE.md` | The definitions of 0 / 1 / 2 used for every passage, with per-question rules |
| `judgments_ai_draft.csv` | The original AI-drafted labels for the first 1,020 passages, before the author's review. Kept so the changes the author made can be compared. |
| `label_flags.csv`, `label_flags.md` | 59 AI-drafted labels flagged for a second look, each with a suggested label and reason (the `.md` is a readable version). Suggestions only; the author's `label` in `judgments.csv` decides. |
| `label_events_<computer>.csv` | A log of every label entered on the labeling page (time, computer, question, passage, label). It is a backup, because cloud sync once overwrote `judgments.csv` with an older copy. The 101 rows are the author's labels for the re-ranker passages. |
| `QUESTIONS_REVIEW.md` | How the 50 questions were checked and approved on 2026-10-17, and what was reworded |
| `queries_draft_2026-10-17.csv` | The original draft questions before that review, kept for comparison with `queries.csv` |

### App log

| File | What it is |
|---|---|
| `query_log.csv` | Searches made in the app when running locally: time, method, question, filters, and top results. Used by `promote.py` to suggest new test questions. The public site doesn't write to it. |

`judgments.xlsx` (the Excel copy of `judgments.csv` for labeling) is created by `eval.pool` and is not in the repo.
`judgments.csv` is the source of truth.

## Reproducing the results

```bash
python -m eval.score                 # rescore from runs.csv and judgments.csv; rewrites results/
```

This needs no API key and no index. `python -m eval.pool` reruns the methods. It needs the dense index, which the app
builds on first launch, and it uses the saved re-ranker answers in `rerank_cache.jsonl`, so no API key is needed for
the 50 questions either.
