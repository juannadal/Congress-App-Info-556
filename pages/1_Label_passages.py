"""Labeling page: judge pooled passages one at a time (0 not relevant, 1 partly relevant, 2 relevant), saving each
label right away.

Opens from the sidebar of the main app (streamlit run app.py). Labels go straight into
eval/judgments.csv, the file eval.score reads; the Excel copy (judgments.xlsx) is re-exported
when you press "Update Excel copy" or finish a batch. Judging is blind: the page never shows which
method found a passage, and it never suggests a label.

Keys: 0 / 1 / 2 to label, B to go back, S to skip (not while typing in the note box).

Review mode (when judgments.csv has ai_label / reviewed columns, i.e. labels were AI-drafted):
the AI draft label and its note are shown; K or Enter keeps it, 0/1/2 changes it, and either
marks the passage reviewed. Progress counts reviewed passages.
"""

import csv
import platform
import re
from datetime import datetime

import pandas as pd
import streamlit as st

from eval.runs import (GROUPS, JUDGMENTS, JUDGMENTS_XLSX, load_queries, read_csv, sync_from_xlsx, write_csv,
                       write_xlsx, xlsx_is_open)
from retrieval.deploy import APP_NAME, PUBLIC_DEMO

FLAGS = JUDGMENTS.parent / "label_flags.csv"  # optional second-opinion list (eval/)
# Every label pressed is also appended to a per-computer log, so labels can be rebuilt if Google Drive sync
# lets one computer overwrite judgments.csv with an older copy (this happened on 2026-10-19/20).
EVENT_LOG = JUDGMENTS.parent / f"label_events_{platform.node().split('.')[0]}.csv"
LABEL_NAMES = {"0": "0 · Not relevant", "1": "1 · Partly relevant", "2": "2 · Relevant"}
BATCH_SIZE = 10  # questions per batch within each group

st.set_page_config(page_title=f"Label passages · {APP_NAME}", page_icon="🏷️", layout="centered")

if PUBLIC_DEMO:  # the public website never shows or saves labels
    st.info("Labeling is turned off on the public site.")
    st.page_link("app.py", label="Go to search", icon="🔎")
    st.stop()


def load_sheet():
    """Read the label file and trim spaces around each label."""
    sheet = read_csv(JUDGMENTS)
    sheet["label"] = sheet["label"].str.strip()
    return sheet


# A wave is one labeling round, such as the first 30 questions and then the rest.
def batches(queries):
    """Labeling batches: waves (if queries.csv has a wave column), then up to BATCH_SIZE questions per group,
    in queries.csv order. Works for any number of questions."""
    # One choice that includes every question.
    out = {"All questions": list(queries["query_id"])}
    # If questions are split into waves, offer the whole wave and each group inside it.
    for wave in sorted(w for w in queries["wave"].unique() if w):
        in_wave = queries[queries["wave"] == wave]
        out[f"Wave {wave}: all {len(in_wave)} questions"] = list(in_wave["query_id"])
        for group in GROUPS:
            ids = list(in_wave.loc[in_wave["group"] == group, "query_id"])
            if ids:
                out[f"Wave {wave}: {group} ({len(ids)})"] = ids
    # Also split each group into smaller batches.
    for group in GROUPS:
        ids = list(queries.loc[queries["group"] == group, "query_id"])
        for i in range(0, len(ids), BATCH_SIZE):
            chunk = ids[i:i + BATCH_SIZE]
            out[f"{group}: {chunk[0]}–{chunk[-1]}"] = chunk
    return out


def highlight(text, query):
    """Bold the question's longer words when they appear in the passage."""
    words = {w for w in re.findall(r"[A-Za-z]{4,}", query)}
    if not words:
        return text
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + r")", re.I)
    return pattern.sub(r"**\1**", text)


# Stop if the label file is missing, or if Excel has the workbook open.
if not JUDGMENTS.exists():
    st.error("No judging sheet yet. In Terminal, run: python -m eval.pool")
    st.stop()
if xlsx_is_open():
    st.error(f"{JUDGMENTS_XLSX.name} is open in Excel. Save and close it, then reload this page, "
             "so the two don't overwrite each other.")
    st.stop()

if "synced" not in st.session_state:  # pick up any labels typed in Excel, once per visit
    st.session_state.synced = sync_from_xlsx()

# Questions still in the test set, the label sheet, and the batch menu.
queries = load_queries()
sheet = load_sheet()
sheet = sheet[sheet["query_id"].isin(queries["query_id"])]  # rows for questions no longer in the set are ignored
options = batches(queries)
flags = {}
if FLAGS.exists():
    f = read_csv(FLAGS)
    flags = {(r.query_id, r.passage_id): (r.suggested_label, r.reason) for r in f.itertuples()}
    options = {f"Flagged for a second look ({len(flags)})": "flagged", **options}
_todo = (sheet["reviewed"] != "yes") if "reviewed" in sheet.columns else (sheet["label"] == "")
if _todo.any():  # e.g. new passages added by the re-ranker; listed first
    options = {f"Still to do ({int(_todo.sum())})": "todo", **options}

# Sidebar: which batch to label, a switch to bold the question's words, and a button to refresh Excel.
with st.sidebar:
    st.header("Batch")
    batch_name = st.selectbox("Questions to label", list(options))
    show_highlight = st.toggle("Bold the question's words", value=False,
                               help="Off by default: bolding exact words can nudge you toward keyword matches.")
    if st.button("Update Excel copy"):
        write_xlsx(load_sheet())
        st.success(f"Re-exported {JUDGMENTS_XLSX.name}.")
    if st.session_state.synced:
        st.info(f"Copied {st.session_state.synced} rows you edited in Excel.")

# Passages in the chosen batch. "Still to do" and "Flagged" are special lists.
if options[batch_name] == "todo":
    rows = sheet[_todo].reset_index()  # 'index' = row in the full CSV
elif options[batch_name] == "flagged":
    in_flags = [(q_, p_) in flags for q_, p_ in zip(sheet["query_id"], sheet["passage_id"])]
    rows = sheet[in_flags].reset_index()  # 'index' = row in the full CSV
else:
    rows = sheet[sheet["query_id"].isin(options[batch_name])].reset_index()  # 'index' = row in the full CSV
review = "reviewed" in sheet.columns  # AI-drafted labels to check
is_done = (lambda df: df["reviewed"] == "yes") if review else (lambda df: df["label"] != "")
verb = "reviewed" if review else "labeled"
labeled = is_done(rows)

# Position: per batch, start at the first unlabeled passage
pos_key = f"pos::{batch_name}"
if pos_key not in st.session_state:
    unlabeled = rows.index[~labeled]
    st.session_state[pos_key] = int(unlabeled[0]) if len(unlabeled) else 0
pos = min(st.session_state[pos_key], len(rows) - 1)

# Progress for this batch, then for every passage on the sheet.
overall_done = int(is_done(sheet).sum())
st.progress(labeled.mean() if len(rows) else 0.0,
            text=f"This batch: {int(labeled.sum())} of {len(rows)} {verb}")
st.progress(overall_done / len(sheet) if len(sheet) else 0.0,
            text=f"All questions: {overall_done} of {len(sheet)} {verb}")
if review:
    changed = int((sheet["reviewed"].eq("yes") & sheet["label"].ne(sheet["ai_label"])).sum())
    st.caption(f"Review mode: you changed {changed} of the AI draft labels so far.")

# A finished batch says so, and writes the Excel copy once.
if labeled.all():
    st.success(f"This batch is fully {verb}. 🎉 Pick another batch in the sidebar.")
    if not st.session_state.get(f"exported::{batch_name}"):
        write_xlsx(load_sheet())
        st.session_state[f"exported::{batch_name}"] = True

row = rows.loc[pos]
q = queries.set_index("query_id").loc[row["query_id"]]
filters = ", ".join(f"{c}: {q[c]}" for c in ("chamber", "party", "state") if q[c])

# The question, any chamber, party, or state filter, and which passage this is.
st.caption(f"Question {row['query_id']} ({row['group']}) · passage {pos + 1} of {len(rows)} in this batch")
st.subheader(q["text"])
if filters:
    st.caption(f"Filter: {filters}")

# Passage card: member, section, and text.
with st.container(border=True):
    st.markdown(f"**{row['member']}**  \n{row['section']}")
    st.markdown(highlight(row["text"], q["text"]) if show_highlight else row["text"])

# The draft label, a second opinion, or the label already saved, then an optional note.
current = row["label"]
has_ai = review and row.get("ai_label", "") != ""  # new passages (e.g. from the re-ranker) have no AI draft
if has_ai:
    st.info(f"AI draft label: **{LABEL_NAMES.get(row['ai_label'], 'none')}**"
            + (f" — {row['ai_note']}" if row["ai_note"] else ""))
    flag = flags.get((row["query_id"], row["passage_id"]))
    if flag:
        st.warning(f"Second opinion: would label it **{LABEL_NAMES.get(flag[0], flag[0])}**. {flag[1]}")
    if row["reviewed"] == "yes":
        st.caption(f"You reviewed this: {LABEL_NAMES.get(current, 'none')}")
elif current:
    st.caption(f"Current label: {LABEL_NAMES[current]}")
st.text_input("Note (optional)", value=row["notes"], key=f"note::{row['index']}")


def save(label):
    """Store this label and note, then move to the next passage that still needs a decision."""
    full = load_sheet()  # re-read so nothing saved elsewhere is lost
    note_now = st.session_state.get(f"note::{row['index']}", "")  # what's in the box at click time
    full.loc[row["index"], ["label", "notes"]] = [label, note_now]
    # Review mode: this passage counts as checked, whether the draft was kept or changed.
    if review:
        full.loc[row["index"], "reviewed"] = "yes"
    write_csv(full, JUDGMENTS)
    # Append the same decision to this computer's log.
    new = not EVENT_LOG.exists()
    with open(EVENT_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "computer", "query_id", "passage_id", "label", "notes"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), platform.node(), row["query_id"],
                    row["passage_id"], label, note_now])
    # Move to the next unfinished passage, or one step forward if the rest are done.
    after = rows.index[(rows.index > pos) & ~labeled]
    st.session_state[pos_key] = int(after[0]) if len(after) else min(pos + 1, len(rows) - 1)


# Buttons: keep the draft, or mark not relevant, partly relevant, or relevant. Each click saves.
if has_ai:
    st.button("✓ Keep AI label", key="keep", use_container_width=True, type="primary",
              on_click=save, args=(row["ai_label"],))
cols = st.columns(3)
for col, (value, name) in zip(cols, LABEL_NAMES.items()):
    col.button(name, key=f"label{value}", use_container_width=True,
               type="primary" if current == value and not review else "secondary", on_click=save, args=(value,))

# Back, skip, and a link to the member's Wikipedia article.
nav = st.columns([1, 1, 3])
nav[0].button("← Back", key="back", disabled=pos == 0,
              on_click=lambda: st.session_state.__setitem__(pos_key, max(pos - 1, 0)))
nav[1].button("Skip →", key="skip", disabled=pos >= len(rows) - 1,
              on_click=lambda: st.session_state.__setitem__(pos_key, min(pos + 1, len(rows) - 1)))
nav[2].link_button("Open Wikipedia article", row["wikipedia_url"])

# Keyboard shortcuts: 0/1/2 label, K or Enter keep the AI label, B back, S skip (ignored while typing)
st.iframe("""
<script>
const doc = window.parent.document;
if (!doc.__labelKeys) {
  doc.__labelKeys = true;
  doc.addEventListener('keydown', (e) => {
    const t = e.target.tagName;
    if (t === 'INPUT' || t === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return;
    const want = {'0': '0 · Not relevant', '1': '1 · Partly relevant', '2': '2 · Relevant',
                  'b': '← Back', 's': 'Skip →', 'k': '✓ Keep AI label', 'enter': '✓ Keep AI label'}[e.key.toLowerCase()];
    if (!want) return;
    const btn = [...doc.querySelectorAll('button')].find(b => b.innerText.trim() === want);
    if (btn && !btn.disabled) { btn.click(); e.preventDefault(); }
  });
}
</script>
""", height=1)
