"""Download the English Wikipedia article for every member in data/members_{congress}.csv.

Steps:
  1. One Wikidata SPARQL query maps each bioguide ID (property P1157) to its
     English Wikipedia article - no guessing by name.
  2. Articles are fetched one at a time from the MediaWiki API as plain text,
     with a pause between requests and maxlag set, to be gentle on Wikimedia.

Outputs:
  data/wikipedia_articles_{congress}.jsonl   one article per line (with full text)
  data/wikipedia_articles_{congress}.csv     same, without the text column
  data/raw/wikipedia/{bioguide_id}.json      cached API responses (reruns skip these)

Usage:
  python scripts/fetch_wikipedia.py
  python scripts/fetch_wikipedia.py --delay 2      # slower
  python scripts/fetch_wikipedia.py --refresh      # re-download everything

Wikimedia asks scripts to identify themselves with contact info. Set
WIKIMEDIA_CONTACT (an email or URL) in the environment or the project .env
to include it in the User-Agent.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from fetch_members import DATA_DIR, PROJECT_ROOT

RAW_DIR = DATA_DIR / "raw" / "wikipedia"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# Members whose Wikidata item is missing a bioguide ID (checked by hand)
MANUAL_TITLES = {
    "J000312": "Jim Justice",
}


def user_agent():
    """Build the name this script sends so Wikimedia knows who is calling."""
    # Use the contact from the environment, or read it from the project .env file.
    contact = os.environ.get("WIKIMEDIA_CONTACT")
    env_file = PROJECT_ROOT / ".env"
    if not contact and env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "WIKIMEDIA_CONTACT" and value.strip():
                contact = value.strip().strip("\"'")
    # Wikimedia wants a short description and a way to reach the project.
    details = "University of Arizona INFO556 class project"
    if contact:
        details += f"; {contact}"
    return f"INFO556-CongressIR/0.1 ({details}) python-requests/{requests.__version__}"


def map_bioguide_to_titles(session, bioguide_ids):
    """Ask Wikidata which English Wikipedia page belongs to each member."""
    # Look up every bioguide ID in one query.
    query = """SELECT ?bioguide ?item ?article WHERE {
      VALUES ?bioguide { %s }
      ?item wdt:P1157 ?bioguide .
      ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> .
    }""" % " ".join(f'"{b}"' for b in bioguide_ids)
    resp = session.post(WIKIDATA_SPARQL, data={"query": query, "format": "json"},
                        headers={"Accept": "application/sparql-results+json"}, timeout=120)
    resp.raise_for_status()

    # Turn each article link into a page title.
    mapping = {}
    for row in resp.json()["results"]["bindings"]:
        url = row["article"]["value"]
        title = requests.utils.unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")
        mapping.setdefault(row["bioguide"]["value"], []).append(
            {"title": title, "wikidata_id": row["item"]["value"].rsplit("/", 1)[1]})
    return mapping


def fetch_article(session, title, max_attempts=6):
    """Fetch one article's plain text. Waits and retries when Wikimedia is busy."""
    # Ask for plain text, follow redirects, and slow down if the servers are busy.
    params = {
        "action": "query", "prop": "extracts|info", "inprop": "url",
        "explaintext": 1, "titles": title, "redirects": 1,
        "format": "json", "formatversion": 2, "maxlag": 5,
    }
    for attempt in range(max_attempts):
        try:
            resp = session.get(WIKIPEDIA_API, params=params, timeout=60)
        except (requests.Timeout, requests.ConnectionError) as e:
            # The connection failed. Wait and try again.
            wait = 5 * 2 ** attempt
            print(f"    {type(e).__name__}, waiting {wait}s")
            time.sleep(wait)
            continue

        # Too many requests, or the server failed. Wait and try again.
        retry_after = int(resp.headers.get("Retry-After", 0) or 0)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = max(retry_after, 5 * 2 ** attempt)
            print(f"    HTTP {resp.status_code}, waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()

        data = resp.json()
        # The servers asked us to slow down. Wait and try again.
        if data.get("error", {}).get("code") == "maxlag":
            wait = max(retry_after, 5)
            print(f"    servers busy (maxlag), waiting {wait}s")
            time.sleep(wait)
            continue
        # A real error, not just a busy server.
        if "error" in data:
            raise RuntimeError(f"API error for {title!r}: {data['error']}")
        return data["query"]["pages"][0]
    # Stop after several failed tries.
    raise RuntimeError(f"Giving up on {title!r} after {max_attempts} attempts")


def main():
    """Download one Wikipedia article per member and save JSONL and CSV files."""
    # Read the Congress, the pause between requests, and whether to ignore saved copies.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--congress", type=int, default=119)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds to pause between article requests (default 1)")
    parser.add_argument("--refresh", action="store_true", help="re-download cached articles")
    args = parser.parse_args()

    # Stop if the member list has not been downloaded yet.
    members_path = DATA_DIR / f"members_{args.congress}.csv"
    if not members_path.exists():
        sys.exit(f"{members_path} not found - run scripts/fetch_members.py first.")
    members = pd.read_csv(members_path, dtype=str).drop_duplicates("bioguide_id")

    # Tell Wikimedia who is calling.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = user_agent()
    print(f"User-Agent: {session.headers['User-Agent']}")

    # Match each member to an English Wikipedia page.
    print(f"Looking up Wikipedia titles on Wikidata for {len(members)} members...")
    mapping = map_bioguide_to_titles(session, members["bioguide_id"].tolist())
    # Add the few members whose Wikidata item has no bioguide ID.
    for bioguide_id, title in MANUAL_TITLES.items():
        mapping.setdefault(bioguide_id, [{"title": title, "wikidata_id": None}])
    multiple = {b: v for b, v in mapping.items() if len(v) > 1}
    if multiple:
        print(f"  warning: {len(multiple)} members map to more than one article; using the first")
    print(f"  matched {sum(b in mapping for b in members['bioguide_id'])}/{len(members)}")

    # Download each article, or reuse the saved copy.
    records, unmatched, failed = [], [], []
    todo = members.to_dict("records")
    for n, member in enumerate(todo, 1):
        bioguide_id = member["bioguide_id"]
        # No page for this person. Report them at the end.
        if bioguide_id not in mapping:
            unmatched.append(member["name"])
            continue
        match = mapping[bioguide_id][0]
        cache = RAW_DIR / f"{bioguide_id}.json"

        if cache.exists() and not args.refresh:
            # Reuse the saved article.
            page = json.loads(cache.read_text(encoding="utf-8"))
        else:
            # Download the article, save it, then pause before the next request.
            print(f"  [{n}/{len(todo)}] {member['name']} -> {match['title']}")
            try:
                page = fetch_article(session, match["title"])
            except Exception as e:  # keep going; report at the end
                print(f"    failed: {e}")
                failed.append(member["name"])
                time.sleep(args.delay)
                continue
            page["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            cache.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
            time.sleep(args.delay)

        # Skip pages that came back with no article text.
        if page.get("missing") or not page.get("extract"):
            failed.append(f"{member['name']} (no article text for {match['title']!r})")
            continue

        # Keep the member info together with the article text.
        text = page["extract"]
        records.append({
            "bioguide_id": bioguide_id,
            "name": member["name"],
            "chamber": member["chamber"],
            "state_code": member["state_code"],
            "party": member["party"],
            "wikidata_id": match["wikidata_id"],
            "wikipedia_title": page["title"],
            "wikipedia_url": page.get("fullurl"),
            "page_id": page.get("pageid"),
            "revision_id": page.get("lastrevid"),
            "fetched_at": page.get("fetched_at"),
            "word_count": len(text.split()),
            "text": text,
        })

    # Save the full text as JSONL, and a CSV without the text.
    df = pd.DataFrame(records)
    jsonl_path = DATA_DIR / f"wikipedia_articles_{args.congress}.jsonl"
    csv_path = DATA_DIR / f"wikipedia_articles_{args.congress}.csv"
    df.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)
    df.drop(columns="text").to_csv(csv_path, index=False, encoding="utf-8")

    print(f"\nSaved {len(df)} articles")
    print(f"  {jsonl_path.relative_to(PROJECT_ROOT)}  (with text)")
    print(f"  {csv_path.relative_to(PROJECT_ROOT)}    (metadata only)")
    print(f"\nWords per article: median {int(df.word_count.median()):,}, "
          f"min {df.word_count.min():,}, max {df.word_count.max():,}, total {df.word_count.sum():,}")
    if unmatched:
        print(f"\nNo Wikipedia article found for {len(unmatched)}: {', '.join(unmatched)}")
    if failed:
        print(f"\nFailed to download {len(failed)}: {', '.join(failed)}")


if __name__ == "__main__":
    main()
