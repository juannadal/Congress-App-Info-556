"""Save each website search to eval/query_log.csv.

The search page calls log_search once per method. Each row records the time, the question,
the filters, and the top 5 passages. Scoring does not call this, so running the evaluation
does not add rows.

The public site sets INFO556_NO_LOG=1, and then this writes nothing. Set INFO556_QUERY_LOG
to save the file somewhere else.
"""

import csv
import os
from datetime import datetime
from pathlib import Path

from retrieval.corpus import PROJECT_ROOT

LOG_PATH = Path(os.environ.get("INFO556_QUERY_LOG", PROJECT_ROOT / "eval" / "query_log.csv"))
LOG_COLUMNS = ["timestamp", "source", "method", "query", "chamber", "party", "state",
               "n_results", "top_passage_ids", "top_members"]
TOP_N = 5


def log_search(method, query, where, results, source="cli", path=LOG_PATH):
    """Append one search to the log. `results` is the DataFrame a search() call returned."""
    # Do nothing when logging is turned off.
    if os.environ.get("INFO556_NO_LOG"):
        return
    # Record the time, the question, the filters, and the top passages.
    where = where or {}
    top = results.head(TOP_N)
    row = {"timestamp": datetime.now().isoformat(timespec="seconds"), "source": source, "method": method,
           "query": query, "chamber": where.get("chamber", ""), "party": where.get("party", ""),
           "state": where.get("state_code", ""), "n_results": len(results),
           "top_passage_ids": "; ".join(top["passage_id"]), "top_members": "; ".join(top["name"])}
    # Create the folder and the file the first time.
    path = Path(path)
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    # BOM only at the start of a new file, so Excel reads accented names as UTF-8
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(row)
