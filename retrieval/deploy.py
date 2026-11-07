"""Settings for running the app as a public website (Cloudflare Containers), and limits on paid API calls.

Secrets come from environment variables first (the Cloudflare Worker passes its secrets this way), then from
~/.info556/.env (a line NAME=value, outside this project so the key is not in the repo). They are never printed.

PUBLIC_DEMO=1 turns on public mode: the labeling page and "Add to queries.csv" are hidden, searches are
not written to eval/query_log.csv, and paid calls (re-ranker, AI overview) are capped per visitor
and per day. Locally (PUBLIC_DEMO unset) nothing is capped.

Caps (public mode only, change them with environment variables):
  PAID_CALLS_PER_SESSION  new paid calls one browser session may make (default 10)
  PAID_CALLS_PER_DAY      new paid calls the whole site may make per day, UTC (default 200)
Cached answers (for example the 50 test questions) are free and don't count.
"""

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

ENV_FILE = Path.home() / ".info556" / ".env"


def get_secret(name, default=None):
    """A setting from the environment, else from ~/.info556/.env, else `default`."""
    value = os.environ.get(name)
    if value:
        return value
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            key, _, val = line.strip().partition("=")
            if key.strip() == name:
                return val.strip().strip('"').strip("'") or default
    return default


def _flag(name):
    """True when a setting is on (1, true, yes, or on)."""
    return str(get_secret(name, "")).strip().lower() in {"1", "true", "yes", "on"}


PUBLIC_DEMO = _flag("PUBLIC_DEMO")
PER_SESSION = int(get_secret("PAID_CALLS_PER_SESSION", 10))
PER_DAY = int(get_secret("PAID_CALLS_PER_DAY", 200))

# One counter for the whole server process (shared by every visitor); resets each UTC day or on restart
_lock = threading.Lock()
_day = {"date": None, "count": 0}

if PUBLIC_DEMO:
    os.environ.setdefault("INFO556_NO_LOG", "1")  # don't log strangers' searches to eval/query_log.csv


def _today():
    """Today's date in UTC, which is when the daily cap resets."""
    return datetime.now(timezone.utc).date().isoformat()


def calls_left():
    """(left this session, left today) in public mode; (None, None) when not capped."""
    if not PUBLIC_DEMO:
        return None, None
    import streamlit as st
    used = st.session_state.get("paid_calls", 0)
    with _lock:
        today = _day["count"] if _day["date"] == _today() else 0
    return max(PER_SESSION - used, 0), max(PER_DAY - today, 0)


def allow_paid_call(kind=""):
    """Say whether one more paid API call is allowed, and count it only when it is. Always True outside public mode.

    `kind` ("rerank", "overview") is only a label; all paid calls share the same caps.
    """
    # No cap when you run the app yourself.
    if not PUBLIC_DEMO:
        return True
    import streamlit as st
    # Stop if this browser has used its own share.
    used = st.session_state.get("paid_calls", 0)
    if used >= PER_SESSION:
        return False
    # Stop if the whole site has used today's share. Otherwise count this call.
    with _lock:
        if _day["date"] != _today():
            _day.update(date=_today(), count=0)
        if _day["count"] >= PER_DAY:
            return False
        _day["count"] += 1
    st.session_state["paid_calls"] = used + 1
    return True


class LimitReached(RuntimeError):
    """Raised when the free AI calls for this visitor or this day are used up."""
    pass


# Public name of the app. GitHub repository names cannot contain spaces, so the repo slug is
# Congress-App-Info-556; this string is what the site and the README show.
APP_NAME = "Congress App Info 556"

LIMIT_MESSAGE = ("The free demo limit for AI features has been reached. Questions that were already answered "
                 "still show their AI results, and BM25, dense, and hybrid search are unlimited.")


def sidebar_nav():
    """On the public site, Streamlit's automatic page list is turned off (so the labeling page is not listed);
    show links to the public pages instead. Does nothing locally."""
    if not PUBLIC_DEMO:
        return
    import streamlit as st
    with st.sidebar:
        st.page_link("app.py", label="Search", icon="🔎")
        st.page_link("pages/2_Results.py", label="Results", icon="📊")
        st.divider()
