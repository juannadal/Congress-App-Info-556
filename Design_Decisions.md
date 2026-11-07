# Design Decisions

The Key Design Decisions section, removed from the proposal on 2026-09-26 to fit the 3-page
limit. Kept here as a record of what was chosen and why. The proposal's Lucene/C# challenge
bullet still summarizes the language and BM25 library choices.

Three decisions shaped the plan. Each was made to keep effort on the research question for how
the retrieval methods compare rather than on infrastructure.

## Corpus: 119th Congress biographies

**Alternative considered:** Wikipedia country articles (the original plan).

About 195 country articles (roughly 2,000 passages) risked being too small to separate the
methods. The new corpus is about 9× larger, every passage links to structured Congress.gov
data through a stable ID, and it mixes exact entities with conceptual career content.

## Language: Python

**Alternative considered:** C# (.NET).

I'm already using Python for my data pipeline, and all the tools I plan to use, like rank_bm25,
sentence-transformers, ChromaDB, Streamlit, and IR evaluation libraries, are native to Python.
On the other hand, C# doesn't have an equivalent to sentence-transformers, which means I'd have
to export MiniLM to ONNX and re-implement its tokenizer and pooling, introducing potential bugs
that aren't related to my research question. The one advantage C# has is Lucene.NET, but it
only covers BM25 and is still in beta.

## BM25 library: rank_bm25

**Alternatives considered:** Apache Lucene (via Pyserini or PyLucene), Lucene.NET,
Elasticsearch/OpenSearch, bm25s, scikit-learn TF-IDF.

Pure Python, one install, and its in-memory scores feed RRF directly. 18,434 passages fit easily
in memory, so Lucene's on-disk index and speed add little. Pyserini requires installing a Java
JDK, which I have little experience with; Elasticsearch requires running a server; TF-IDF is a
weaker baseline. Lucene, studied in Module 5, remains the production reference, and an optional
check compares rankings against Pyserini.
