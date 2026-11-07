"""Build a dataset of every member of the House and Senate for one Congress.

Uses the Congress.gov API:
  1. GET /v3/member/congress/{congress}   -> list of everyone who served
  2. GET /v3/member/{bioguideId}           -> full details for each member

Outputs (in data/):
  members_{congress}.csv    one row per member per chamber served in that Congress
  members_{congress}.json   the same rows as JSON
  raw/members/{id}.json     cached API detail responses (reruns skip these)

Usage:
  python scripts/fetch_members.py              # 119th Congress
  python scripts/fetch_members.py --congress 118
  python scripts/fetch_members.py --refresh    # ignore the cache

The API key is read from CONGRESS_API_KEY, or from a .env file in the
project root or congress-api/.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

API_BASE = "https://api.congress.gov/v3"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "members"


def load_api_key():
    """Read the Congress.gov key from the environment or a .env file."""
    if os.environ.get("CONGRESS_API_KEY"):
        return os.environ["CONGRESS_API_KEY"]
    for env_file in (PROJECT_ROOT / ".env", PROJECT_ROOT / "congress-api" / ".env"):
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "CONGRESS_API_KEY" and value.strip():
                    return value.strip().strip("\"'")
    sys.exit("No CONGRESS_API_KEY found (set it in the environment or a .env file).")


def get_json(session, url, params=None, retries=5):
    """GET a URL, retrying on rate limits and server errors."""
    for attempt in range(retries):
        # Wait longer after each failed try.
        wait = 2 ** attempt
        try:
            resp = session.get(url, params=params, timeout=60)
        except (requests.Timeout, requests.ConnectionError) as e:
            # The connection failed. Wait and try again.
            print(f"  {type(e).__name__} on {url}, retrying in {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504):
            # The server is busy or broken. Wait and try again.
            print(f"  HTTP {resp.status_code} on {url}, retrying in {wait}s")
            time.sleep(wait)
            continue
        # Any other error is a real failure. Stop.
        resp.raise_for_status()
    # Stop after several failed tries.
    raise RuntimeError(f"Giving up on {url} after {retries} attempts")


def fetch_member_list(session, congress):
    """Download every member who served in this Congress."""
    members, offset = [], 0
    # The list arrives 250 people at a time. Keep asking until it is complete.
    while True:
        page = get_json(session, f"{API_BASE}/member/congress/{congress}",
                        {"limit": 250, "offset": offset})
        members.extend(page["members"])
        total = page["pagination"]["count"]
        print(f"  listed {len(members)}/{total}")
        if len(members) >= total or not page["members"]:
            return members
        offset += 250


def fetch_member_detail(session, bioguide_id, refresh):
    """Download one member's full record, or reuse the saved copy."""
    cache = RAW_DIR / f"{bioguide_id}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    detail = get_json(session, f"{API_BASE}/member/{bioguide_id}")["member"]
    cache.write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding="utf-8")
    return detail


def build_rows(listing, detail, congress):
    """One row per chamber the member served in during this Congress."""
    # Keep only the terms from this Congress.
    terms = [t for t in detail.get("terms", []) if t.get("congress") == congress]
    address = detail.get("addressInformation", {})
    party_history = detail.get("partyHistory", [])

    # Write one row for each chamber they served in.
    rows = []
    for term in terms:
        rows.append({
            "bioguide_id": detail["bioguideId"],
            "name": detail.get("directOrderName"),
            "first_name": detail.get("firstName"),
            "last_name": detail.get("lastName"),
            "chamber": "Senate" if term["chamber"] == "Senate" else "House",
            "member_type": term.get("memberType"),
            "state": term.get("stateName"),
            "state_code": term.get("stateCode"),
            "district": term.get("district", listing.get("district")),
            "party": party_history[-1]["partyName"] if party_history else listing.get("partyName"),
            "party_code": party_history[-1].get("partyAbbreviation") if party_history else None,
            "term_start_year": term.get("startYear"),
            "term_end_year": term.get("endYear"),
            "current_member": detail.get("currentMember"),
            "birth_year": detail.get("birthYear"),
            "website": detail.get("officialWebsiteUrl"),
            "office_address": address.get("officeAddress"),
            "phone": address.get("phoneNumber"),
            "sponsored_bills": detail.get("sponsoredLegislation", {}).get("count"),
            "cosponsored_bills": detail.get("cosponsoredLegislation", {}).get("count"),
            "image_url": detail.get("depiction", {}).get("imageUrl"),
            "api_url": f"{API_BASE}/member/{detail['bioguideId']}",
        })
    return rows


def main():
    """Download the members for one Congress and save CSV and JSON files."""
    # Read which Congress to fetch, and whether to ignore saved copies.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--congress", type=int, default=119)
    parser.add_argument("--refresh", action="store_true", help="re-download cached details")
    args = parser.parse_args()

    # Make the cache folder and send the API key with every request.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.params = {"api_key": load_api_key(), "format": "json"}

    # Download the short list, then the full record for each person.
    print(f"Fetching member list for the {args.congress}th Congress...")
    listing = fetch_member_list(session, args.congress)

    print(f"Fetching details for {len(listing)} members...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        details = list(pool.map(
            lambda m: fetch_member_detail(session, m["bioguideId"], args.refresh), listing))

    # Turn each person into one row per chamber.
    rows = []
    for item, detail in zip(listing, details):
        member_rows = build_rows(item, detail, args.congress)
        if not member_rows:
            print(f"  warning: no {args.congress}th Congress term found for {item['bioguideId']}")
        rows.extend(member_rows)

    # Sort the rows and save them as CSV and JSON.
    df = pd.DataFrame(rows).sort_values(["chamber", "state", "district", "last_name"],
                                        na_position="first")
    df["district"] = df["district"].astype("Int64")

    csv_path = DATA_DIR / f"members_{args.congress}.csv"
    json_path = DATA_DIR / f"members_{args.congress}.json"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_json(json_path, orient="records", indent=2, force_ascii=False)

    print(f"\nSaved {len(df)} rows ({df['bioguide_id'].nunique()} people)")
    print(f"  {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"  {json_path.relative_to(PROJECT_ROOT)}")
    print("\nBy chamber and member type:")
    print(df.groupby(["chamber", "member_type"]).size().to_string())
    print("\nBy chamber and party:")
    print(df.groupby(["chamber", "party"]).size().to_string())
    print("\nCurrently serving:", int(df.drop_duplicates("bioguide_id")["current_member"].sum()))


if __name__ == "__main__":
    main()
