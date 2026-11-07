# Congress Bio Search: design handoff

The interface design for the INFO 556 final project, "Keywords, Meaning, or Both? Evaluating Search over Biographies of the 119th Congress". Everything here is plain files, so any editor can read and change it.

"Congress Bio Search" is a working title. Rename it freely.

## What is in this folder

| Path | What it is |
|---|---|
| `screens/*.html` | The four screens as static HTML and CSS, no JavaScript. Open one in a browser to see it. These are the reference for layout, copy and markup. |
| `screenshots/*.png` | Each screen in light and dark, for a quick look without a browser. |
| `design-system/README.md` | The rules: voice, colour, type, spacing, layout. Read this before changing the interface. |
| `design-system/tokens.json` | Every colour (light and dark), type style, spacing step, radius and shadow, each with a usage note. The source of truth. |
| `design-system/tokens.css` | The same tokens as CSS variables, plus the `@font-face` rules. Compiled from `tokens.json`; keep the two in step. |
| `design-system/components/bundle.css` | Styles for the eight components (classes start with `cb-`). |
| `design-system/components/*.md` | One guideline per component: what it is for, what you pass it, the do's and don'ts. |
| `design-system/components/bundle.js`, `index.d.ts` | The components as React (global `window.BioSearch`) and their prop types. Only needed if you build a React front end; Streamlit does not use them. |
| `design-system/fonts/` | Source Serif 4, IBM Plex Sans, IBM Plex Mono (woff2). Open Font License, see `design-system/licenses/`. |
| `canvas-source/` | The original design-canvas files (`.dc.html`). Keep them if you want to republish the canvas, otherwise ignore them. |

## The screens

| File | Screen | Covers, from the proposal |
|---|---|---|
| `screens/start.html` | Start | A question in everyday words; the three example questions; what Keyword, Meaning and Hybrid do. |
| `screens/results.html` | Search results | Ranked passages; filters for chamber, party and state; each result's member, chamber, party, state, portrait, matching text and Wikipedia link. |
| `screens/compare.html` | Compare methods | The side-by-side results: one question, three rankings. |
| `screens/evaluation.html` | Evaluation | nDCG@10, Recall@10 and MRR per method and question group; filtering before versus after the search; the hand-labelled judgments. |

To see the dark theme, change `data-theme="light"` to `data-theme="dark"` on the first `div` of a screen.

## What is placeholder

- The members, passages and scores on every screen are invented sample data. They are not real members of Congress. Replace them with real results from the corpus.
- Every evaluation value is a bracketed placeholder, because the evaluation has not been run.
- The footer shows `[SNAPSHOT DATE]`; fill in the date of the Wikipedia snapshot.
- Filters and the method switch are drawn in one state. They do not change the results in these static files.
- There is no logo and no icon set. The name is set in plain type.

## Working on it

1. Put this folder in the repository, for example as `design/`.
2. Note in the project instructions that the interface design lives in `design/`, and to read `design/README.md` and `design/design-system/README.md` before changing the UI.
3. Ask for what you want in terms of these files. Some prompts that work well:
   - "Read design/README.md, then build the Streamlit search page to match design/screens/results.html, using the real BM25 index."
   - "Render each search result with the markup of the `cb-result` card in design/screens/results.html, filled from my passage metadata."
   - "Change the hybrid method colour in design/design-system/tokens.json and tokens.css, in both themes, and keep 4.5:1 contrast on the paper grounds."
   - "Add a state picker to design/screens/results.html following the FilterChip guideline."

## Building it in Streamlit

The proposal names Streamlit for the interface. A workable mapping, to check against your Streamlit version:

- **Tokens and component styles.** Load `tokens.css` and `bundle.css` once at the top of the app (read the files and inject them in a `<style>` block with `st.html` or `st.markdown(..., unsafe_allow_html=True)`). The font files need to be served by the app (Streamlit's static file serving) and the `url(...)` paths in `tokens.css` pointed at them; without that the system fallback fonts are used and the layout still holds.
- **Result cards, party tags, method tags, relevance labels, metric tiles.** Render these as HTML strings with the `cb-` classes, copying the markup from `screens/*.html`. Escape passage text before inserting it, and wrap only the matched terms in `<mark>`.
- **Search box, filters, method switch, buttons.** Use Streamlit's own widgets (`st.text_input`, `st.pills` or `st.multiselect`, `st.segmented_control` or `st.radio`, `st.button`) and style them toward the design with the theme settings below. They will not match the static screens pixel for pixel; the layout, wording and order should.
- **Side by side.** Three `st.columns`, always in the order Keyword, Meaning, Hybrid.
- **Theme.** A starting point for `.streamlit/config.toml`, taken from the light theme tokens:

```toml
[theme]
base = "light"
primaryColor = "#1b1915"              # ink
backgroundColor = "#f6f3ea"           # paper
secondaryBackgroundColor = "#ece7da"  # paper-sunk
textColor = "#1b1915"                 # ink
```

## The rules that matter most

The full set is in `design-system/README.md`. The ones that are easiest to break:

- **Three voices, three typefaces.** Serif for words from the corpus (member names, passage text). Sans for the interface. Mono for anything computed (ranks, scores, metrics, counts).
- **Each colour has one job.** Ink is the brand colour and the primary action. The yellow highlight marks matched words in a passage and nothing else. The three method colours identify Keyword, Meaning and Hybrid. Party colours appear only in the party tag, always beside the letter D, R or I.
- **Even-handed.** No colouring of cards, rows or charts by party; parties listed alphabetically; no adjectives about members.
- **No invented numbers.** A metric that has not been computed shows a placeholder, never a made-up value.
- **Say where it came from.** Every passage links to its Wikipedia article, and the footer says Wikipedia is not a verified source.
