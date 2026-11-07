# ResultCard

One ranked passage and the member it is about: rank, portrait, name, chamber, party, state, the matching text, a link to the source, and the score.

**You provide:** `rank`, `name`, `chamber` ("Senator" or "Representative"), `party` ("D", "R" or "I"), `state` (full name), optionally `district`, `photo`, `href` (the Wikipedia article) and `score` (already formatted, e.g. "BM25 14.82"). The passage is the children: plain text with each matched term wrapped in a `mark` element.

- The name and the passage are set in serif because they come from the corpus; the rank and score are mono because the system computed them.
- Quote the passage as it appears in the article. Do not summarise, trim mid-sentence, or add an ellipsis the source does not have.
- Wrap only the words that matched in `mark`. For meaning-based results with no shared words, leave the passage unmarked rather than guessing.
- Without `photo` the card shows the member's initials on `paper-sunk`. Do not substitute a stock portrait.
- Stack cards with `space-6` between them in a single list, or `space-4` inside a side-by-side column. In a column narrower than 360px the portrait may be dropped.
- The member in this preview is an invented placeholder, not a real member of Congress.
