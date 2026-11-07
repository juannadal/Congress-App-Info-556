# MetricTile

One evaluation metric for one method: the metric's name, its value, the method, and a one-line note.

**You provide:** `label` (exactly "nDCG@10", "Recall@10" or "MRR"), `value` (a string, already formatted to three decimals), `method`, and optionally `note` (the query group or sample size: "20 keyword queries").

- Lay tiles out as a grid: one row per metric, one column per method, in the order Keyword, Meaning, Hybrid, with `space-4` gutters.
- The value is mono at the `metric` size. Do not colour the value by method or by whether it won; say which method scored highest in a sentence beneath the grid.
- Report a difference as significant only when the test says so, and say which test.
- The values in this preview are zeroes on purpose: the evaluation has not been run. Never ship invented numbers in a tile.
