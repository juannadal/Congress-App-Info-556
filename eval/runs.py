"""Helpers for the test questions, the saved rankings, and the label sheet.
A label is 0 (not relevant), 1 (partly relevant), or 2 (relevant).
A pool is the set of passages put on that sheet.

Test queries, the judging sheet, and running every method over the queries.

Files (all in eval/):
  queries.csv    query_id, group (keyword | conceptual | filtered), text, chamber, party, state,
                 wave (optional labeling order: 1 = first 30 questions, 2 = the rest), notes
  runs.csv       each method's ranked list per query (written by eval.pool, read by eval.score),
                 so the scores are computed on exactly the rankings that were pooled and judged
  judgments.csv  the judging sheet: one row per (query, passage) in the pool, label 0/1/2
  judgments.xlsx the same sheet formatted for labeling in Excel (wrapped text, 0/1/2 drop-down).
                 judgments.csv is the source of truth. Rows whose label or notes were changed in the
                 .xlsx are copied into the CSV (by query_id + passage_id) before pooling or scoring,
                 and the .xlsx is then re-exported. The labeling page (pages/1_Label_passages.py)
                 writes to the CSV directly.

CSV files are written as UTF-8 with a byte-order mark so Excel shows accented names correctly.
"""

import os
from pathlib import Path

import pandas as pd

EVAL_DIR = Path(__file__).resolve().parent
QUERIES = EVAL_DIR / "queries.csv"
RUNS = EVAL_DIR / "runs.csv"
JUDGMENTS = EVAL_DIR / "judgments.csv"
JUDGMENTS_XLSX = EVAL_DIR / "judgments.xlsx"
RESULTS_DIR = EVAL_DIR / "results"

GROUPS = ("keyword", "conceptual", "filtered")
METHODS = ("bm25", "dense", "hybrid", "rerank")  # canonical order; "rerank" only when it has been run
BASE_METHODS = METHODS[:3]
LABELS = (0, 1, 2)  # not relevant, partly relevant, relevant
FILTER_COLUMNS = {"chamber": "chamber", "party": "party", "state": "state_code"}


def read_csv(path):
    """Read a project CSV as text, so a blank cell stays blank."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def write_csv(df, path):
    """Write atomically (temp file, then rename) so an interrupted save never leaves a half-written file."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, path)


def load_queries(path=QUERIES):
    """Load the test questions and stop if an id is missing, repeated, or not in a known group."""
    q = read_csv(path)
    # Need an id, a group, and text. Fill filter columns when an older file lacks them.
    for col in ("query_id", "group", "text"):
        if col not in q.columns:
            raise SystemExit(f"{path} needs a {col!r} column")
    for col in ("chamber", "party", "state", "wave", "notes"):
        if col not in q.columns:
            q[col] = ""
    # Drop a blank id, trim spaces, and reject a repeated id or an unknown group.
    q = q[q["query_id"].str.strip() != ""].copy()
    q = q.apply(lambda c: c.str.strip())
    if q["query_id"].duplicated().any():
        raise SystemExit(f"duplicate query_id in {path}: {sorted(q.loc[q['query_id'].duplicated(), 'query_id'])}")
    bad = q.loc[~q["group"].isin(GROUPS), "query_id"].tolist()
    if bad:
        raise SystemExit(f"group must be one of {GROUPS}; check {bad}")
    # Store state filters in capitals, such as CA.
    q["state"] = q["state"].str.upper()
    return q.reset_index(drop=True)


# Turn a question's chamber, party, and state into the filter the search uses.
def where_of(query):
    """A query row's chamber/party/state columns -> the `where` dict the search modules take."""
    return {field: query[col] for col, field in FILTER_COLUMNS.items() if query[col]}


def filter_label(query):
    """Short sheet text for the filters that are set, such as chamber=Senate."""
    return ", ".join(f"{col}={query[col]}" for col in FILTER_COLUMNS if query[col])


# Search every test question with each method and keep the ranked passages.
def make_runs(queries, depth=10, with_rerank=False):
    """Run BM25, dense, and hybrid (plus the re-ranker if asked) on every query; return the top `depth`
    of each as a long table. Re-ranker answers come from eval/rerank_cache.jsonl when cached."""
    from retrieval.corpus import load_passages
    from retrieval.hybrid import HybridIndex

    # Word search, meaning search, and the mix of both live on one index.
    index = HybridIndex(load_passages())
    # Stop if the meaning index is missing or stale. The message says how to build it.
    if not index.dense.is_current():
        raise SystemExit(f"{index.dense.name} is missing or out of date. Start the website once; it builds the meaning index.")
    searchers = {"bm25": index.bm25.search, "dense": index.dense.search, "hybrid": index.search}
    # The re-ranker reorders the mixed results. A saved answer is reused when one exists.
    if with_rerank:
        from retrieval.rerank import LLMReranker
        searchers["rerank"] = LLMReranker(index).search
    rows = []
    # One row per question, method, and rank.
    for q in queries.to_dict("records"):
        for method in searchers:
            hits = searchers[method](q["text"], k=depth, where=where_of(q))
            for hit in hits.itertuples():
                rows.append({"query_id": q["query_id"], "method": method, "rank": hit.rank,
                             "passage_id": hit.passage_id, "score": hit.score})
    return pd.DataFrame(rows, columns=["query_id", "method", "rank", "passage_id", "score"])


# Column order and widths for the Excel sheet: what's needed to judge first, the label next to the text
XLSX_COLUMNS = [("query_id", 9), ("query", 26), ("filter", 12), ("member", 24), ("section", 24), ("text", 90),
                ("label", 7), ("notes", 24), ("passage_id", 13), ("group", 11), ("wikipedia_url", 40)]
# Hidden columns holding each row's label and notes as exported, so a sync only copies rows changed in Excel
BASELINE = {"label": "label_at_export", "notes": "notes_at_export"}


def xlsx_is_open(path=JUDGMENTS_XLSX):
    """True when Excel has the label workbook open."""
    return (path.parent / f"~${path.name}").exists()


def _clean_label(series):
    """Clean a cell from Excel, so 2.0 becomes 2 and an empty cell stays blank."""
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True).replace("nan", "")


def sync_from_xlsx(csv_path=JUDGMENTS, xlsx_path=JUDGMENTS_XLSX):
    """Copy rows whose label or notes were changed in Excel into the CSV, then re-export the Excel file.

    Only rows that differ from the hidden values written at export are copied, so an out-of-date Excel
    file never overwrites labels saved elsewhere (e.g. from the labeling page). Skipped while Excel has
    the file open, since the re-export can't happen then. Returns the number of rows copied.
    """
    # Skip when a file is missing or Excel still has the workbook open.
    if not (xlsx_path.exists() and csv_path.exists()) or xlsx_is_open(xlsx_path):
        return 0
    edited = pd.read_excel(xlsx_path, dtype=str, keep_default_na=False)
    if not set(BASELINE.values()) <= set(edited.columns):
        return 0  # an older export without baselines; leave the CSV alone
    for col, base in BASELINE.items():
        edited[col], edited[base] = _clean_label(edited[col]), _clean_label(edited[base])
    # Rows whose label or note differs from the last export.
    changed = edited[(edited["label"] != edited["label_at_export"]) | (edited["notes"] != edited["notes_at_export"])]
    if changed.empty:
        return 0
    # Copy those cells into the CSV, matching on question id and passage id.
    sheet = read_csv(csv_path)
    updates = changed.set_index(["query_id", "passage_id"])[["label", "notes"]]
    key = pd.MultiIndex.from_frame(sheet[["query_id", "passage_id"]])
    found = key.isin(updates.index)
    sheet.loc[found, ["label", "notes"]] = updates.loc[key[found]].to_numpy()
    write_csv(sheet, csv_path)
    # Rewrite the workbook so its hidden snapshot matches the CSV again.
    write_xlsx(sheet, xlsx_path)
    return int(found.sum())


def write_xlsx(sheet, path=JUDGMENTS_XLSX):
    """Write the judging sheet as a formatted Excel workbook (wrapped text, frozen header, 0/1/2 drop-down)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "judgments"
    # Columns a person needs in order to judge, plus hidden copies of the label and note at export time.
    names = [c for c, _ in XLSX_COLUMNS] + list(BASELINE.values())
    ws.append(names)
    shade = PatternFill("solid", fgColor="EEF3FA")
    shaded, last = False, None
    for i, row in enumerate(sheet.to_dict("records"), start=2):
        label = str(row.get("label", "")).strip()
        values = {**row, "label": int(label) if label in {"0", "1", "2"} else "",
                  "label_at_export": label, "notes_at_export": row.get("notes", "")}
        ws.append([values.get(c, "") for c in names])
        # Switch the shade when the question changes, so one question stays one block.
        if row["query_id"] != last:
            shaded, last = not shaded, row["query_id"]
        for cell in ws[i]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if shaded:
                cell.fill = shade
    for j, name in enumerate(names, start=1):
        letter = ws.cell(row=1, column=j).column_letter
        ws.cell(row=1, column=j).font = Font(bold=True)
        # Hide the snapshot columns. They exist only to spot later edits.
        if name in BASELINE.values():
            ws.column_dimensions[letter].hidden = True
            continue
        ws.column_dimensions[letter].width = dict(XLSX_COLUMNS)[name]
        # The label column accepts only 0, 1, or 2.
        if name == "label":
            dv = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True,
                                error="Use 0 (not relevant), 1 (partly relevant), or 2 (relevant).",
                                errorTitle="Label must be 0, 1, or 2", showErrorMessage=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}{ws.max_row}")
            for cell in ws[letter][1:]:
                cell.alignment = Alignment(horizontal="center", vertical="top")
    # Keep the header on screen and turn on column filters.
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(XLSX_COLUMNS)).column_letter}{ws.max_row}"
    wb.save(path)


# Read the labels as numbers. A blank means not judged yet, and Excel edits are copied in first.
def load_judgments(path=JUDGMENTS):
    """The judging sheet with `label` as a nullable int (blank = not judged yet).
    Rows changed in judgments.xlsx are copied in first (see sync_from_xlsx)."""
    # The real sheet also picks up labels typed in Excel.
    if path == JUDGMENTS:
        sync_from_xlsx()
    sheet = read_csv(path)
    raw = sheet["label"].str.strip()
    # Stop if a label is not 0, 1, 2, or blank.
    bad = sheet.loc[~raw.isin(["", *map(str, LABELS)]), ["query_id", "passage_id", "label"]]
    if len(bad):
        raise SystemExit(f"labels must be 0, 1, 2, or blank; fix these rows in {path}:\n{bad.to_string(index=False)}")
    sheet["label"] = pd.to_numeric(raw.replace("", None)).astype("Int64")
    return sheet
