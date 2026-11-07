Congress Bio Search is a search tool over the Wikipedia biographies of the members of the 119th Congress. A person types a question in everyday words and gets a ranked list of passages, each tied to the member it is about. The same question can be answered three ways (keyword, meaning, or both), and the tool exists to show which works best. It is a student research project, not an official product of Congress: no seals, flags, eagles, star fields or government-site styling, anywhere.

## Content fundamentals

**Plain words, the reader's own.** Write the way the questions are asked: "members who were teachers before entering politics", "California representatives who were prosecutors". The interface says **Keyword**, **Meaning** and **Hybrid**; the technique names (BM25, MiniLM, RRF) follow in mono, as detail, never as the label.

**Factual and even-handed.** The subject is careers, committees, backgrounds and roles. No adjectives about members, no commentary on positions, no ranking of people. A result is "a passage that matches", never "the best member".

**Say where it came from.** Every passage links to its Wikipedia article. Wikipedia is not a verified source; say so once, plainly, in the page footer, and cite the recorded revision ID in mono.

- Sentence case everywhere: headings, buttons, chips. Only `eyebrow` labels are capitals.
- Address the reader as "you". The system does not say "I" or "we".
- Call the unit a **passage**, not a chunk, snippet or document. Call the people **members**; a member is a **Senator** or a **Representative**.
- Metric names are exact: **nDCG@10**, **Recall@10**, **MRR**. Values have three decimals: `0.742`.
- Party is a letter and a word: "D Democrat", "R Republican", "I Independent". Listed together, alphabetical.
- States are spelled out ("California"), with the House district after: "California 12th district".
- No emoji, no exclamation marks. An empty result says what happened and what to try: "No passages match with these filters. Remove a filter to search all members."

## Visual foundations

**Three voices, three typefaces.** This is the rule the whole system hangs on.

| Voice | Family | Styles | What it sets |
|---|---|---|---|
| The source | Source Serif 4 (`--font-serif`) | `display`, `member-name`, `passage` | Words that come from the corpus: member names and passage text. Also the page title. |
| The interface | IBM Plex Sans (`--font-sans`) | `heading`, `body`, `label`, `caption`, `eyebrow` | Everything the application says: controls, labels, help. |
| The computed | IBM Plex Mono (`--font-mono`) | `metric`, `score` | Numbers the system produced: ranks, scores, metrics, counts, revision IDs. |

Never set interface copy in serif or a passage in sans. If a number was computed, it is mono, with tabular figures.

**Colour is quiet, and each hue has one job.**

- The page is `paper`; cards, tiles and the search field are `paper-raised`; inset wells are `paper-sunk`. Text is `ink`, secondary text `ink-muted`; both read on all three grounds.
- **Ink is the brand colour.** The primary button and a selected filter chip are an `ink` fill with `on-ink` text. Links are `ink`, underlined. There is no blue link colour and no accent hue for actions.
- `mark` is the highlighter: the background behind words in a passage that matched the query, with `on-mark` text at weight 600. It appears nowhere else: not on buttons, not for "best score", not as decoration.
- `method-keyword`, `method-semantic` and `method-hybrid` identify the three retrieval methods in tags, column headers and chart series, each on its `-soft` tint or on a paper ground. They differ in lightness as well as hue; still, label every series directly.
- `party-dem`, `party-rep` and `party-ind` appear only inside `PartyTag`, always beside the letter. Never colour a card, row, name, filter chip or chart by party.
- Relevance grades have no colour. They are ink pips and a word.
- There is no error red and no success green. State a problem in a sentence, in `ink`.

Both themes carry every token. The dark theme lightens the method and party colours, so text on them is never literal white: use the tokens.

**Borders, not shadows.** Cards and tiles sit flat on a 1px `rule` hairline. Controls (inputs, quiet buttons, unselected chips) take `rule-strong`, which holds 3:1 on every ground. `shadow-pop` is for things that float (the state picker) and nothing else.

**Small, square-ish corners.** `radius-md` (4px) for buttons, inputs, cards and tiles; `radius-sm` (2px) for highlights, tags and the portrait; `radius-full` only for filter chips and relevance pips.

**Spacing is a 4px scale.** `space-4` pads cards and tiles and separates side-by-side columns; `space-6` separates result cards in a list and the search bar from the filter row; `space-8` separates page sections.

**Focus.** Every control shows `focus-ring` on keyboard focus: a 2px gap in the page colour, then 2px of solid ink. Do not remove it or replace it with a colour change.

**States.** Hover on a quiet control fills it with `paper-sunk`. Selected is the ink fill. Disabled is a dashed `rule-strong` outline with `ink-muted` text. No opacity fades.

**Motion.** None is defined. Results replace each other without animation; a slow search shows the words "Searching all passages" in `caption`, not a spinner.

**Layout.**

- Search page: page title in `display`, then `SearchBar` (720px at most), then the filter row, then results. A single ranked list is one column, 720px at most, so a passage stays under 68 characters a line.
- Compare view: three equal columns in the fixed order Keyword, Meaning, Hybrid, each headed by a `MethodTag`, with `space-4` gutters. The same rank sits on the same row across columns where heights allow.
- Evaluation page: a grid of `MetricTile`s (one row per metric, one column per method), then tables. Table headers sit on `paper-sunk`; rows divide with `rule`.
- Page margins are `space-12` top and bottom, `space-6` at the sides; content is 1200px at most.

**Imagery.** The only images are members' portraits, 56 by 72, in a result card. Where there is none, show initials on `paper-sunk`. No stock photography, no illustrations, no Capitol dome.

## Iconography

There is no icon set and no logo. Set the name "Congress Bio Search" in Source Serif 4 at weight 600 wherever a mark would go. The interface uses words for every action; the only glyphs are typographic: the north-east arrow (↗) after a link that leaves for Wikipedia, and the middle dot (·) between pieces of metadata. If a later screen truly needs icons, choose one outline set, 1.5px stroke, drawn in `ink`, and record it here before using it.
