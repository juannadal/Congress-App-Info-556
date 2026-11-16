# Congress App Info 556

Search over biographies of the 119th Congress. Class project for INFO/ISTA 456/556 (Text Retrieval and Web Search), University of Arizona, Fall 2026.

It compares four ways to search 18,434 Wikipedia passages about the 555 members of the 119th Congress:
BM25 (keyword), dense embeddings (all-MiniLM-L6-v2 + ChromaDB), hybrid (Reciprocal Rank Fusion), and a
a re-ranker over the hybrid top 20. Methods are scored with nDCG@10, Recall@10, and MRR on 50 test
questions (20 keyword, 20 conceptual, 10 filtered by chamber, party, or state) using pooled relevance labels.

**Try it:** https://congress-search.juannadal.workers.dev (no install needed; the first visit after a quiet spell takes about 30 seconds to wake up).

## How it works

### Step 1: gather the biographies and build the indexes (done once)

```mermaid
flowchart LR
  A["Congress.gov API<br/>555 members"] --> B["Wikidata<br/>member ID → article"]
  B --> C["Wikipedia<br/>555 biographies<br/>1.41M words"]
  C --> D["Chunker<br/>one passage per paragraph<br/>≤ 256 tokens"]
  D --> E[("18,434<br/>passages")]
  E --> F["BM25 index<br/>rank_bm25"]
  E --> G["Dense index<br/>MiniLM → ChromaDB"]
```

Members are matched to their Wikipedia articles by their official Congress ID (Wikidata property P1157), not by
name. Reference lists and other non-prose sections are dropped. Every passage keeps its member's chamber, party, and
state for filtering. Code: `scripts/`.

### Step 2: search by keywords and by meaning, then fuse (every search)

```mermaid
flowchart LR
  Q["Question<br/>+ filters"] --> F1{"Filter<br/>chosen?"}
  F1 -- yes --> PF["Only matching members<br/>(pre-filter)"]
  F1 -- no --> ALL["All 18,434<br/>passages"]
  PF --> BM["BM25<br/>top 100 by keywords"]
  PF --> DN["Dense<br/>top 100 by meaning"]
  ALL --> BM
  ALL --> DN
  BM --> RRF["Hybrid (RRF)<br/>score = Σ 1 / (60 + rank)"]
  DN --> RRF
```

Chamber, party, and state filters are applied before ranking. BM25 keeps its word statistics from the whole corpus,
so a filtered search scores passages the same way an unfiltered one does. Code: `retrieval/bm25.py`,
`retrieval/dense.py`, `retrieval/hybrid.py`.

### Step 3: re-rank, then summarize with Grok (every search, optional)

```mermaid
flowchart LR
  H["Hybrid<br/>top 20"] --> R1{"Re-ranker<br/>on?"}
  R1 -- no --> OUT["Final<br/>ranking"]
  R1 -- yes --> C1{"Already<br/>cached?"}
  C1 -- yes --> OUT
  C1 -- no --> CL["The re-ranker reads all 20<br/>and reorders them"]
  CL --> OUT
  OUT --> O1{"AI overview<br/>on?"}
  O1 -- yes --> GK["Grok writes 2–5 sentences<br/>from the top 8 passages,<br/>citing each one as [n]"]
  O1 -- no --> UI["Results page<br/>4 columns side by side"]
  GK --> UI
```

Every re-ranker answer is cached, so the 50 test questions cost nothing and the evaluation can be repeated exactly. On
the public site each browser session can make up to 10 new paid AI calls, shared by the re-ranker and the overview (a
new question can use one of each), within a site-wide daily cap of 200. The overview never changes a ranking. Code:
`retrieval/rerank.py`, `retrieval/overview.py`.

### The algorithms

| Method | How it scores a passage | nDCG@10 |
|---|---|---|
| BM25 (keyword) | Term frequency × inverse document frequency, normalized for passage length (rank_bm25, k1 = 1.5, b = 0.75, stemming, NLTK stop words) | 0.624 |
| Dense (meaning) | Cosine similarity between all-MiniLM-L6-v2 embeddings of the question and the passage (384 dimensions, ChromaDB) | 0.589 |
| Hybrid (RRF) | Sum of 1 / (60 + rank) over the BM25 and dense top 100, so the two score scales never have to be compared | 0.730 |
| Re-ranker | A model reads the question and the hybrid's top 20 passages and returns their order as JSON (listwise re-ranking) | 0.959 |

Scores are over 50 test questions (20 keyword, 20 conceptual, 10 filtered). Hybrid beats both BM25 and dense
(randomization test, Holm-corrected p < 0.01). Full results, including per-group scores and significance tests, are
in `eval/results/` and on the app's Results page.

### Two decisions about the AI models

- **A model re-ranks the results.** Putting 20 passages in order is a careful comparison task, and it is a search
  method, so it is scored like the other three. The questions are factual (who was a prosecutor, who was born
  abroad), not opinion. Caveat: most relevance labels were drafted by AI and reviewed by the author, which may
  flatter an AI re-ranker.
- **Grok (xAI) writes the AI overview.** Questions about members of Congress are political by nature, and Grok
  answers them directly from the passages it is given. The overview is a display layer only: Grok may
  use only those passages, must cite each claim as [n], and the page says it can be wrong.
  `OVERVIEW_ENABLED=0` turns it off.

## Layout

```
app.py                  Streamlit search page: four methods side by side (streamlit run app.py)
pages/
  1_Label_passages.py   Labeling page: judge pooled passages 0 / 1 / 2 (hidden on the public site)
  2_Results.py          Results page: scores, significance tests, and per-question results
retrieval/              The search methods, used by the app and the evaluation
  corpus.py             Loads the passages and applies chamber / party / state filters
  bm25.py               BM25 keyword search
  dense.py              Dense (meaning) search: MiniLM embeddings in ChromaDB
  hybrid.py             Hybrid search: Reciprocal Rank Fusion of BM25 and dense
  rerank.py             LLM re-ranker over the hybrid top 20, with a response cache
  overview.py           Grok AI overview of the top results (display only)
  deploy.py             Settings, API keys, and paid-call limits for the public site
  querylog.py           Logs app searches to eval/query_log.csv
eval/                   Test questions, relevance labels, scoring, and results (see eval/README.md)
scripts/                Data collection and chunking, run once in order (see data/README.md)
data/                   The corpus, member data, and portraits (see data/README.md)
design/                 Interface design: screen mockups, design tokens, fonts (see design/README.md)
congress-api/           A small Congress.gov API test script and the API key template
windows/                One-click setup and start scripts for Windows
Dockerfile, cloudflare/, DEPLOY.md   The public website (Cloudflare Worker + Container)
requirements.txt        Python packages
```

More detail: [data/README.md](data/README.md) describes every data file and column, and
[eval/README.md](eval/README.md) describes the evaluation files and workflow. Every Python file starts with a
docstring that explains what it does and how to run it.

### Code reference

All four search methods have the same interface, so the app and the evaluation can treat them the same way:
`search(query, k=10, where=None)` returns a pandas DataFrame of the top `k` passages, with `rank`, `score`, and the
passage columns (`passage_id`, `bioguide_id`, `name`, `chamber`, `party`, `state_code`, `section`, `text`,
`wikipedia_url`). `where` is an optional filter such as `{"chamber": "Senate", "state_code": ["CA", "TX"]}`.

| Module | Main parts |
|---|---|
| `retrieval/corpus.py` | `load_passages(congress=119)` reads `data/passages_119.jsonl`; `filter_mask(passages, where)` gives the passages that match a filter |
| `retrieval/bm25.py` | `tokenize(text)`; `BM25Index(passages).search(...)`, and `.scores(query, where)` for the raw scores |
| `retrieval/dense.py` | `DenseIndex(passages)`: `.build()` embeds the passages, `.is_current()` checks whether the saved index matches the data, `.search(...)` |
| `retrieval/hybrid.py` | `rrf(rankings)` fuses ranked lists; `HybridIndex(passages).search(...)` also returns each passage's `bm25_rank` and `dense_rank` |
| `retrieval/rerank.py` | `LLMReranker(hybrid).search(...)` re-orders the hybrid top 20 and returns `hybrid_rank` too |
| `retrieval/overview.py` | `status()`, `select_sources(hits)`, `stream_overview(query, where, sources)`, `link_citations(text, sources)` |
| `retrieval/deploy.py` | `get_secret(name)` reads a setting from the environment or `~/.info556/.env`; `allow_paid_call()` enforces the public-site limits |
| `eval/runs.py` | `load_queries()`, `make_runs(queries)` runs every method on every question, and label-sheet input and output |
| `eval/score.py` | Metric functions (nDCG, Recall, MRR) and significance tests; `python -m eval.score` |

Example:

```python
from retrieval.corpus import load_passages
from retrieval.hybrid import HybridIndex

index = HybridIndex(load_passages())
index.search("former prosecutor", k=5, where={"state_code": "CA"})
```

### Rebuilding the data (optional)

The processed data is already in `data/`, so this is not needed to run the app or reproduce the results. To collect
it again, get a free Congress.gov API key at [api.data.gov/signup](https://api.data.gov/signup/), copy
`congress-api/.env.example` to `.env` in the project root, add the key, and run:

```bash
python scripts/fetch_members.py          # members from Congress.gov
python scripts/fetch_wikipedia.py        # their Wikipedia articles, matched by ID through Wikidata
python scripts/chunk_wikipedia.py        # split the articles into passages
python scripts/fetch_member_images.py    # portraits
python scripts/fetch_sponsored_bills.py  # sponsored legislation (not used by search)
```

This downloads the *current* data, which will differ from the committed files and no longer match the relevance
labels. See [data/README.md](data/README.md#how-the-files-were-made).

## Run it on your own computer

You don't need to install anything to try the app: use the public site linked at the top. To run it locally, pick
one of the three options below. Each one needs an internet connection the first time.

### What you need

- **Python 3.10, 3.11, 3.12, or 3.13.** Newer versions (3.14 and up) may not have PyTorch packages yet, so the install
  can fail. Check with `python3 --version`. If needed, install 3.12 from [python.org](https://www.python.org/downloads/).
- **Git**, to download the project. Alternatively, use **Code > Download ZIP** on GitHub and unzip it.
- About **3 GB of free disk space**, mostly for PyTorch.
- **API keys are optional.** Keyword, meaning, and hybrid search work without any key.

> **Note:** The two AI features, the **Claude re-ranker** and the **Grok AI overview**, do not work without your own
> API keys. The only exception is the re-ranker on the 50 test questions, whose answers are saved in
> `eval/rerank_cache.jsonl`. The author's keys are not included in this project. To turn the AI features on, see
> [Optional: AI features](#optional-ai-features).

Everything else is included or downloads by itself. The repo includes the 18,434 passages, member data, portraits,
test questions, and relevance labels. The first run downloads the MiniLM model (about 90 MB) and the NLTK stop-word
list.

### Option A: Mac or Linux

```bash
git clone https://github.com/juannadal/Congress-App-Info-556.git
cd Congress-App-Info-556

# Create a virtual environment (use any Python 3.10–3.13, e.g. python3.12)
python3.12 -m venv ~/.info556/venv
source ~/.info556/venv/bin/activate

# Install CPU-only PyTorch first (the default package is several GB larger), then the rest
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Start the app
streamlit run app.py
```

Your browser opens http://localhost:8501. The first launch builds the meaning-search index. This takes about 20
seconds on Apple silicon and can take a few minutes on older computers. Later launches are fast.

To run it again later:

```bash
cd Congress-App-Info-556
source ~/.info556/venv/bin/activate
streamlit run app.py
```

Press `Ctrl+C` in the terminal to stop the app.

### Option B: Windows

1. Install Python 3.11, 3.12, or 3.13 from [python.org](https://www.python.org/downloads/). During the install, check
   **"Add python.exe to PATH"**.
2. Download the project: `git clone https://github.com/juannadal/Congress-App-Info-556.git`, or use the ZIP from
   GitHub.
3. Double-click `windows\setup_windows.bat` once. It creates the environment, installs the packages, and builds the
   search index (allow 5–15 minutes).
4. Double-click `windows\start_app.bat` to start the app. It opens the "Label passages" page; click **app** at the
   top of the sidebar to get to the search page. Close the window to stop the app.

### Option C: Docker (any operating system)

If you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed, this avoids installing Python
yourself:

```bash
git clone https://github.com/juannadal/Congress-App-Info-556.git
cd Congress-App-Info-556
docker build -t congress-search .        # 10–20 minutes the first time
docker run -p 8080:8080 congress-search
```

Then open http://localhost:8080. This runs the public-site version, which hides the labeling page and limits paid AI
calls.

### Optional: AI features

The app works without these keys. Without them, the re-ranker column only shows results for the 50 saved test
questions, and the AI overview is unavailable.

| Feature | Uses | Key name | Where to get a key |
|---|---|---|---|
| Re-ranker (new questions) | Claude (Anthropic) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) > **API Keys** |
| AI overview | Grok (xAI) | `XAI_API_KEY` | [console.x.ai](https://console.x.ai/) > **API Keys** |

Both services charge per use and need a payment method or prepaid credits on your account. Each search costs a few
cents at most. Setting a low monthly spending limit in each console is a good idea. You can add one key, both, or
neither.

**1. Get a key.** Sign in to the console linked above, create a new API key, and copy it. It is shown only once.

**2. Save it where the app can find it.** Create a folder named `.info556` in your home folder, and in it a text file
named `.env`:

- Mac/Linux: `~/.info556/.env`
- Windows: `%USERPROFILE%\.info556\.env` (for example `C:\Users\yourname\.info556\.env`)

Put one key per line, with no spaces or quotes. Leave out any line you don't need:

```
ANTHROPIC_API_KEY=your-key-here
XAI_API_KEY=your-key-here
```

On Windows, Notepad may save the file as `.env.txt`. In the save dialog, choose **Save as type: All files** to avoid
that.

**3. Restart the app.** Stop it (`Ctrl+C`, or close the window on Windows) and start it again.

Other ways to provide the keys:

- **Environment variables:** run `export ANTHROPIC_API_KEY=...` (Mac/Linux) or `set ANTHROPIC_API_KEY=...` (Windows)
  in the same terminal, before `streamlit run app.py`.
- **Docker:** add `-e ANTHROPIC_API_KEY=... -e XAI_API_KEY=...` to the `docker run` command.

**Keep your keys private.** Never commit the `.env` file or paste a key into the project folder. The `.env` file lives
outside the project, and `.gitignore` also blocks `.env` files, so they don't end up on GitHub by accident.

### Troubleshooting

- **`pip install torch` fails with "No matching distribution":** your Python is too new or too old. Make the
  virtual environment with Python 3.10–3.13.
- **SSL / certificate error when the app starts (Mac):** Python from python.org needs its certificates installed once.
  Open *Applications > Python 3.x* and double-click **Install Certificates.command**, then restart the app.
- **Port 8501 is already in use:** run `streamlit run app.py --server.port 8502` and open http://localhost:8502.
- **`git status` shows `eval/query_log.csv` changed:** that's expected. The app logs local searches there.

### Reproducing the evaluation

With the environment activated, from the project folder:

```bash
python -m eval.score    # scores all four methods on the 50 test questions from the saved rankings and labels
```

Results are written to `eval/results/` and shown on the app's Results page.

## Use of generative AI

A generative model helped write and test the code and drafted the first version of the test questions. Most
relevance labels were drafted by an AI tool and reviewed by the author; passages added by the re-ranker were
labeled by the author.
