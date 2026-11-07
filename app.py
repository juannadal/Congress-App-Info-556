"""Search Congress biographies and compare four methods side by side.

Word match (BM25) looks for the question's words. Meaning match (dense) looks for the same idea.
Hybrid mixes those two lists. The re-ranker then reorders hybrid's short list.

Launch from the project root:
  streamlit run app.py

Every search is logged to eval/query_log.csv (one row per method, source "app"), and the
sidebar can add the current question to eval/queries.csv.
"""

import pandas as pd
import streamlit as st

from eval.promote import add_query
from eval.runs import GROUPS
from retrieval.corpus import DATA_DIR, load_passages
from retrieval.deploy import (
    APP_NAME, LIMIT_MESSAGE, PUBLIC_DEMO, LimitReached, allow_paid_call, calls_left, sidebar_nav,
)
from retrieval import overview
from retrieval.hybrid import HybridIndex
from retrieval.querylog import log_search
from retrieval.rerank import LLMReranker

IMAGE_DIR = DATA_DIR / "images" / "members"
METHODS = {"rerank": "Re-ranker", "hybrid": "Hybrid (RRF)", "bm25": "BM25 (keyword)", "dense": "Dense (meaning)"}
SNIPPET = 350

st.set_page_config(page_title=APP_NAME, page_icon="🏛️", layout="wide")


@st.cache_resource(show_spinner="Loading the indexes (first time only)...")
def load_index():
    """Load the search tools, and build the meaning search the first time on this machine."""
    index = HybridIndex(load_passages())
    if not index.dense.is_current():  # first run on a new computer or server: embed the passages (~20 s to a few min)
        index.dense.build()
    return index


index = load_index()


@st.cache_resource
def load_reranker():
    """Prepare the re-ranker once and reuse it for later searches."""
    return LLMReranker(index)


passages = index.passages

# Sidebar: filters, result count, and adding the question to the test set
# On the public site, links to Search and Results sit above the filters.
sidebar_nav()
with st.sidebar:
    # Chamber, party, state, how many results, and switches for one member, the re-ranker, and an overview.
    st.header("Filters")
    chamber = st.selectbox("Chamber", ["Any", "House", "Senate"])
    party = st.selectbox("Party", ["Any", *sorted(passages["party"].unique())])
    state = st.selectbox("State", ["Any", *sorted(passages["state_code"].unique())])
    k = st.slider("Results per method", 5, 20, 10)
    per_member = st.toggle("One result per member", value=True,
                           help="Results are passages, so one member can match several times. When on, each member "
                                "appears once (best passage first) with the other matches tucked underneath. "
                                "The evaluation scores still count passages.")
    session_left, _ = calls_left()
    use_rerank = st.toggle("Re-ranker", value=True,
                           help="Re-orders hybrid's top 20. Test questions are cached (free); "
                                "a new question costs about 2 cents."
                                + (f" You have {session_left} new AI questions left in this visit."
                                   if session_left is not None else ""))
    overview_ok, overview_reason = overview.status()
    use_overview = st.toggle("AI overview (Grok)", value=overview_ok, disabled=not overview_ok,
                             help=overview_reason or "A short answer written by Grok from the top results, with "
                                  "numbered links to the sources. It doesn't change any ranking.")

# Page heading and how many members and passages can be searched.
st.title(APP_NAME)
st.caption(f"Search the 119th Congress: {passages['bioguide_id'].nunique()} members, "
           f"{len(passages):,} Wikipedia passages. Each method's top results are shown side by side.")

# Search box. Nothing runs until Search is pressed.
with st.form("search"):
    query = st.text_input("Question", placeholder='e.g. "former prosecutor" or "grew up on a farm"')
    submitted = st.form_submit_button("Search", type="primary")

# Sidebar filters that are not "Any".
where = {f: v for f, v in [("chamber", chamber), ("party", party), ("state_code", state)] if v != "Any"}

# Search only when the form is submitted, so other clicks don't re-run (and re-log) the search
if submitted and query.strip():
    fetch = k * 3 if per_member else k  # fetch more so k distinct members can be shown
    results = {"hybrid": index.search(query, k=fetch, where=where),
               "bm25": index.bm25.search(query, k=fetch, where=where),
               "dense": index.dense.search(query, k=fetch, where=where)}
    # The re-ranker is optional. If it cannot run, the other methods still show.
    if use_rerank:
        try:
            results = {"rerank": load_reranker().search(query, k=fetch, where=where,
                                                        allow_call=lambda: allow_paid_call("rerank")),
                       **results}
        except LimitReached:
            st.info(LIMIT_MESSAGE)
        except (SystemExit, Exception) as e:  # no key, network, or API error: show the other three
            st.warning(f"Re-ranker unavailable: {e}")
    # Record each method's top hits.
    for method, hits in results.items():
        log_search(method, query, where, hits.head(k), source="app")
    # Keep this search on the page so later clicks do not run it again.
    st.session_state["last"] = {"query": query.strip(), "where": where, "results": results, "k": k,
                                "per_member": per_member, "use_overview": use_overview}

last = st.session_state.get("last")

# Lower sidebar, hidden on the public site: save this search as a test question.
if not PUBLIC_DEMO:  # adding test questions is for Juan only, not the public site
    with st.sidebar:
        st.divider()
        st.header("Test questions")
        if last:
            st.write(f"Add **{last['query']}**" + (f" ({', '.join(last['where'].values())})" if last["where"] else "")
                     + " to eval/queries.csv")
            group = st.radio("Group", GROUPS, index=2 if last["where"] else 0, horizontal=True)
            if st.button("Add to queries.csv"):
                w = last["where"]
                qid, added = add_query(last["query"], group, w.get("chamber", ""), w.get("party", ""),
                                       w.get("state_code", ""))
                if added:
                    st.success(f"Added as {qid}.")
                else:
                    st.info(f"Already in queries.csv as {qid}.")
        else:
            st.write("Run a search to add it to your test questions.")


def show_result(r, method, position, more=None):
    """Show one hit: photo, name, rank notes, and a short bit of the passage."""
    portrait = IMAGE_DIR / f"{r.bioguide_id}.jpg"
    left, right = st.columns([1, 4])
    # Photo on the left. Name, party, state, and chamber on the right.
    with left:
        if portrait.exists():
            st.image(str(portrait), width=64)
    with right:
        st.markdown(f"**{position}. [{r.name}]({r.wikipedia_url})**  \n{r.party} · {r.state_code} · {r.chamber}")
        # Where hybrid had this passage before the re-ranker moved it.
        if method == "rerank":
            st.caption(f"Hybrid #{r.hybrid_rank}")
        # Where the word search and the meaning search had ranked it.
        if method == "hybrid":
            ranks = [f"{name} #{int(v)}" if pd.notna(v) else f"{name} –"
                     for name, v in (("BM25", r.bm25_rank), ("Dense", r.dense_rank))]
            st.caption(" · ".join(ranks))
    # Section name and a short clip. The rest of the passage opens on demand.
    st.caption(r.section)
    text = r.text if len(r.text) <= SNIPPET else r.text[:SNIPPET].rsplit(" ", 1)[0] + " …"
    st.write(text)
    if len(r.text) > SNIPPET:
        with st.expander("Full passage"):
            st.write(r.text)
    # Other passages from this member, when the sidebar asks for one result per member.
    if more is not None and len(more):
        with st.expander(f"{len(more)} more matching passage{'s' if len(more) > 1 else ''} for {r.name}"):
            for m in more.itertuples():
                st.caption(f"#{m.rank} · {m.section}")
                st.write(m.text)
    st.divider()


# The user sees a short overview above the columns, with the passages it used listed underneath.
def show_overview(last):
    """Grok's overview of the best ranking shown (re-ranker if it ran, else hybrid). Generated once per
    search and kept in session state, so other clicks don't call the API again."""
    results = last["results"]
    # Prefer the re-ranker's list when it ran. Otherwise use the mixed results.
    best = results.get("rerank", results["hybrid"])
    sources = overview.select_sources(best)
    if sources is None or sources.empty:
        return
    with st.container(border=True):
        st.markdown("**AI overview**")
        # Write the overview once per search. Later clicks reuse the saved text.
        if "overview" not in last:
            box = st.empty()
            box.caption("Grok is reading the top results and writing an overview…")
            text = ""
            try:
                for piece in overview.stream_overview(last["query"], last["where"], sources):
                    text += piece
                    box.markdown(text + " ▌")
                last["overview"] = text
            except overview.OverviewError as e:
                last["overview"], last["overview_error"] = None, str(e)  # don't retry on every click
            box.empty()
        # Show the answer with source links, or the error from the last try.
        if last.get("overview"):
            st.markdown(overview.link_citations(last["overview"], sources))
            with st.expander(f"Sources ({len(sources)} passages from the "
                             f"{'re-ranker' if 'rerank' in results else 'hybrid'} results)"):
                st.markdown(overview.sources_markdown(sources))
            st.caption(f"Written by Grok ({overview.model()}) from the passages above. It can be wrong; "
                       "check the sources.")
        else:
            st.info(last.get("overview_error", "No overview."))


if last:
    # An empty Search still warns, and the previous results stay on screen.
    if submitted and not query.strip():
        st.warning("Type a question first.")
    # Result heading, including any chamber, party, or state filter.
    shown = ", ".join(last["where"].values())
    st.markdown(f"Results for **{last['query']}**" + (f" ({shown})" if shown else ""))
    # Reserve the overview's spot above the columns, but fill it after the results are drawn,
    # so a slow Grok answer never holds up the search results
    overview_slot = st.container() if last.get("use_overview") else None
    # One column per method that returned results.
    shown_methods = {m: t for m, t in METHODS.items() if m in last["results"]}
    columns = st.columns(len(shown_methods))
    for col, (method, title) in zip(columns, shown_methods.items()):
        with col:
            st.subheader(title)
            hits = last["results"][method]
            if hits.empty:
                st.write("No matching passages.")
            # Best passage per member, with that member's other hits tucked underneath.
            if last.get("per_member"):
                best = hits.drop_duplicates("bioguide_id").head(last["k"])
                for pos, r in enumerate(best.itertuples(), start=1):
                    more = hits[(hits["bioguide_id"] == r.bioguide_id) & (hits["passage_id"] != r.passage_id)]
                    show_result(r, method, pos, more)
            # Or the top passages in rank order.
            else:
                for pos, r in enumerate(hits.head(last.get("k", len(hits))).itertuples(), start=1):
                    show_result(r, method, pos)
    if overview_slot is not None:
        with overview_slot:
            show_overview(last)
elif submitted:
    # Search was pressed before any results exist, and the box was empty.
    st.warning("Type a question first.")
