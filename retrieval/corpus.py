"""Load the passage corpus and apply chamber, party, and state filters.

This is the only module that knows where the corpus lives. The search code needs just a
DataFrame with `passage_id` and a text column; the metadata columns are used for filters
and display, so another corpus can be swapped in by changing this file.
"""

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Columns a query can be filtered on, e.g. {"chamber": "Senate", "state_code": ["CA", "TX"]}
FILTER_FIELDS = ("chamber", "party", "state_code")

# Columns returned with each search result
DISPLAY_COLUMNS = ["passage_id", "bioguide_id", "name", "chamber", "party", "state_code",
                   "section", "text", "wikipedia_url"]


def load_passages(congress=119, path=None):
    """Read the saved passages for one Congress, one row per passage."""
    path = Path(path) if path else DATA_DIR / f"passages_{congress}.jsonl"
    # Keep the ids as text so they are not read as numbers.
    df = pd.read_json(path, lines=True, dtype={"bioguide_id": str, "passage_id": str})
    return df.reset_index(drop=True)


def filter_mask(passages, where):
    """Boolean mask of passages matching every field in `where` (a value or a list of values)."""
    mask = pd.Series(True, index=passages.index)
    for field, value in (where or {}).items():
        if field not in FILTER_FIELDS:
            raise ValueError(f"can't filter on {field!r}; use one of {FILTER_FIELDS}")
        values = value if isinstance(value, (list, tuple, set)) else [value]
        mask &= passages[field].isin(values)
    return mask.to_numpy()
