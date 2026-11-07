# SearchBar

The one place a person types a question, with the only primary button on the page.

**You provide:** `onSubmit(query)`, and either `value` + `onChange` (controlled) or `defaultValue`. It fills the width of its container; give it a container no wider than 720px on a results page.

- Put it at the top of the page, above the filter row, with `space-6` between them.
- Keep the placeholder as an instruction in plain words ("Ask in everyday words"), never an example that looks like a filled-in query.
- A query is a question or a phrase in the person's own words: "members who were teachers before entering politics". Do not ask for operators, quotes or field names.
- Filters do not go inside the field. Chamber, party and state are `FilterChip`s beneath it.
