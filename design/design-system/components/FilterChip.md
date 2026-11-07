# FilterChip

A toggle that narrows results to one chamber, party or state.

**You provide:** the filter's value as children ("Senate", "California"), `selected`, an `onClick` that flips it, and optionally `count` (matching passages with the filter on).

- Group chips by kind in this order: chamber, party, state. Put an `eyebrow` label before each group and `space-2` between chips.
- Selected is an ink fill with `on-ink` text; unselected is a `rule-strong` outline. The state is also exposed as `aria-pressed`.
- Party chips say the word ("Democrat"), never a letter alone, and never take the party colours. Party colour belongs to `PartyTag` only.
- With 50 states, show the selected state as a chip and put the rest behind a picker; do not render 50 chips.
- `count` is set in mono because it is a computed number.
