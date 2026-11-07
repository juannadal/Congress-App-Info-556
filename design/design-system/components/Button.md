# Button

Quiet is the default; primary is the ink fill and appears once per view.

**You provide:** the label as children, `onClick`, and `variant="primary"` for the one action the view is for.

- On the search page the primary button is Search, inside `SearchBar`. Everything else ("Clear filters", "Compare methods") is quiet.
- Labels are verb first, sentence case, two or three words.
- Disabled is a dashed outline with `ink-muted` text, so it reads as unavailable without relying on a fainter colour.
- Links out to Wikipedia are underlined text links (`.cb-link`), not buttons.
