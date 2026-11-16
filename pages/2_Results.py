"""Results page: evaluation scores for every method, significance tests, and a per-question explorer.

nDCG@10 rewards relevant passages near the top of the 10 results. Recall@10 is the share of relevant passages found in
the top 10. MRR is 1 divided by the rank of the first relevant passage.

Reads what eval.score wrote (eval/results/summary.csv, significance.csv, per_query.csv) plus
eval/runs.csv and eval/judgments.csv for the example explorer. Rerun python -m eval.score after
labels change, then reload this page.
"""

from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from eval.runs import GROUPS, JUDGMENTS, RESULTS_DIR, RUNS, load_queries, read_csv
from retrieval.deploy import APP_NAME, sidebar_nav

st.set_page_config(page_title=f"Results · {APP_NAME}", page_icon="📊", layout="wide")
# On the public site, the sidebar links to Search and Results.
sidebar_nav()

# Fixed color per method (validated categorical palette, slots 1-4), so a method keeps its color everywhere
NAMES = {"bm25": "BM25 (keyword)", "dense": "Dense (meaning)", "hybrid": "Hybrid (RRF)", "rerank": "Re-ranker"}
COLORS = {"bm25": "#2a78d6", "dense": "#eb6834", "hybrid": "#1baf7a", "rerank": "#eda100"}
METRICS = {"ndcg": "nDCG@10", "recall": "Recall@10", "mrr": "MRR"}
SCOPES = {"all": "All 50", "keyword": "Keyword (20)", "conceptual": "Conceptual (20)", "filtered": "Filtered (10)"}
MARK = {"2": "✅ relevant", "1": "🟡 partly", "0": "❌ not relevant", "": "· unjudged"}


@st.cache_data
def load(mtime):
    """Read the score tables, the saved rankings, and the labels."""
    summary = pd.read_csv(RESULTS_DIR / "summary.csv")
    sig = pd.read_csv(RESULTS_DIR / "significance.csv")
    per_query = pd.read_csv(RESULTS_DIR / "per_query.csv", dtype={"query_id": str})
    runs = read_csv(RUNS)
    runs["rank"] = runs["rank"].astype(int)
    judgments = read_csv(JUDGMENTS)
    return summary, sig, per_query, runs, judgments


summary_path = RESULTS_DIR / "summary.csv"
# Stop and ask for scores if they have not been written yet.
if not summary_path.exists():
    st.error("No results yet. In Terminal, run: python -m eval.score")
    st.stop()
mtime = summary_path.stat().st_mtime
summary, sig, per_query, runs, judgments = load(mtime)
methods = [m for m in NAMES if m in set(summary["method"])]
queries = load_queries().set_index("query_id")

# Heading: how many questions and labeled passages, and when these scores were computed.
# Pooled passages are each method's top 10, mixed into the label sheet.
st.title("Results")
st.caption(f"{len(per_query['query_id'].unique())} test questions (20 keyword, 20 conceptual, 10 filtered) · "
           f"{len(judgments):,} judged passages, pooled from each method's top 10 · scored "
           f"{datetime.fromtimestamp(mtime):%b %d, %Y %I:%M %p}")
st.caption("Labels: 0 = not relevant, 1 = partly relevant, 2 = relevant. Most labels were drafted by an AI tool and "
           "reviewed by me; the passages added by the re-ranker were labeled by me from scratch.")

# Choose the score used by the chart and the tables below.
metric = st.radio("Metric", list(METRICS), format_func=METRICS.get, horizontal=True)

# Bar chart: one cluster per question type, one color per method, with the score printed on each bar.
# Grouped bars: one group per question type, one bar per method, value labels on every bar
data = summary[summary["method"].isin(methods)].copy()
data["Method"] = data["method"].map(NAMES)
data["Questions"] = data["scope"].map(SCOPES)
data["Score"] = data[metric].round(3)
color = alt.Scale(domain=[NAMES[m] for m in methods], range=[COLORS[m] for m in methods])
base = alt.Chart(data).encode(
    x=alt.X("Questions:N", sort=list(SCOPES.values()), title=None, axis=alt.Axis(labelAngle=0)),
    xOffset=alt.XOffset("Method:N", sort=[NAMES[m] for m in methods]),
)
bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="white", strokeWidth=2).encode(
    y=alt.Y("Score:Q", title=METRICS[metric], scale=alt.Scale(domain=[0, 1.05])),
    color=alt.Color("Method:N", scale=color, legend=alt.Legend(title=None, orient="top")),
    tooltip=["Questions", "Method", alt.Tooltip("Score:Q", format=".3f"), "n"],
)
# The number just above each bar.
labels = base.mark_text(dy=-6, fontSize=11).encode(y="Score:Q", text=alt.Text("Score:Q", format=".2f"))
st.altair_chart((bars + labels).properties(height=360), width="stretch")

# The same scores as a table, tucked away until opened.
with st.expander("Table view"):
    table = data.pivot(index="Method", columns="Questions", values="Score")[list(SCOPES.values())]
    st.dataframe(table.loc[[NAMES[m] for m in methods]], width="stretch")

# Pair table: the score gap, and whether it is larger than chance.
# Holm means the bar is higher because many pairs are tested together.
# Significance: paired randomization test, Holm-adjusted within each metric and question group
st.subheader("Are the differences real?")
scope = st.selectbox("Questions", list(SCOPES), format_func=SCOPES.get)
s = sig[(sig["metric"] == metric) & (sig["scope"] == scope)].copy()
s["Comparison"] = s["method_b"].map(NAMES) + " vs " + s["method_a"].map(NAMES)
s["Difference"] = s["mean_diff_b_minus_a"].map("{:+.3f}".format)
s["p (Holm)"] = s["p_rand_holm"].map(lambda p: "< 0.001" if p < 0.001 else f"{p:.3f}")
s["Significant (p < 0.05)?"] = s["p_rand_holm"].map(lambda p: "✅ yes" if p < 0.05 else "— no")
st.dataframe(s[["Comparison", "Difference", "p (Holm)", "Significant (p < 0.05)?"]], hide_index=True,
             width="stretch")
st.caption("Difference = first method minus second, averaged over the questions. p from a paired randomization "
           "(sign-flip) test, Holm-adjusted for the number of method pairs; a Wilcoxon test is in significance.csv.")

# One question at a time: each method's top 10, marked relevant, partly relevant, or not.
# Example explorer: each method's top 10 for one question, marked with the judged label
st.subheader("Look at one question")
labels_of = dict(zip(zip(judgments["query_id"], judgments["passage_id"]), judgments["label"]))
passage_info = judgments.drop_duplicates("passage_id").set_index("passage_id")
options = list(queries.index)
default = options.index("f01") if "f01" in options else 0


def describe(qid):
    """Menu text for one question: its id, wording, and any chamber, party, or state filter."""
    q = queries.loc[qid]
    filters = ", ".join(q[c] for c in ("chamber", "party", "state") if q[c])
    return f"{qid} · {q['text']}" + (f" ({filters})" if filters else "")


qid = st.selectbox("Question", options, index=default, format_func=describe)
scores = per_query[per_query["query_id"] == qid].set_index("method")
cols = st.columns(len(methods))
for col, m in zip(cols, methods):
    with col:
        # This method's scores, then its top 10 passages and the judged mark.
        st.markdown(f"**{NAMES[m]}**")
        if m in scores.index:
            st.caption(f"nDCG@10 {scores.loc[m, 'ndcg']:.2f} · Recall@10 {scores.loc[m, 'recall']:.2f} · "
                       f"MRR {scores.loc[m, 'mrr']:.2f}")
        top = runs[(runs["query_id"] == qid) & (runs["method"] == m)].sort_values("rank").head(10)
        for r in top.itertuples():
            info = passage_info.loc[r.passage_id] if r.passage_id in passage_info.index else None
            mark = MARK.get(labels_of.get((qid, r.passage_id), ""), "")
            name = info["member"] if info is not None else r.passage_id
            st.markdown(f"{r.rank}. {mark}  \n**{name}**")
            if info is not None:
                with st.expander("Passage"):
                    st.caption(info["section"])
                    st.write(info["text"])

# Every question on the chosen score. When both ran, the biggest re-ranker gain is listed first.
# Per-question table, sorted by how much the best method beats hybrid
st.subheader("Every question")
wide = per_query.pivot(index="query_id", columns="method", values=metric)[methods]
wide.columns = [NAMES[m] for m in methods]
wide.insert(0, "Question", [queries.loc[q, "text"] for q in wide.index])
wide.insert(0, "Group", [queries.loc[q, "group"] for q in wide.index])
if "rerank" in methods and "hybrid" in methods:
    wide["Re-ranker − Hybrid"] = wide[NAMES["rerank"]] - wide[NAMES["hybrid"]]
    wide = wide.sort_values("Re-ranker − Hybrid", ascending=False)
st.dataframe(wide.round(3), width="stretch")
st.caption(f"{METRICS[metric]} per question. Files: eval/results/per_query.csv, summary.csv, significance.csv.")
