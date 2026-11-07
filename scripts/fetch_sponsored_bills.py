"""Fetch the legislation sponsored by every member in data/members_{congress}.csv.

Uses GET /v3/member/{bioguideId}/sponsored-legislation, which returns each
member's whole career (not just the one Congress), mixing bills/resolutions
with amendments. They are split into two files:

  data/sponsored_bills_{congress}.csv        bills and resolutions (have titles)
  data/sponsored_amendments_{congress}.csv   amendments (no title in this endpoint)
  data/raw/sponsored/{id}.json               cached API responses per member

Run scripts/fetch_members.py first.

Usage:
  python scripts/fetch_sponsored_bills.py              # members of the 119th
  python scripts/fetch_sponsored_bills.py --congress 118
  python scripts/fetch_sponsored_bills.py --refresh    # ignore the cache
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

from fetch_members import API_BASE, DATA_DIR, PROJECT_ROOT, get_json, load_api_key

RAW_DIR = DATA_DIR / "raw" / "sponsored"


def fetch_all_pages(session, bioguide_id, limit):
    """Download every page of bills and amendments this member sponsored."""
    items, offset = [], 0
    while True:
        page = get_json(session, f"{API_BASE}/member/{bioguide_id}/sponsored-legislation",
                        {"limit": limit, "offset": offset})
        items.extend(page["sponsoredLegislation"])
        total = page["pagination"]["count"]
        if len(items) >= total or not page["sponsoredLegislation"]:
            return items, total
        offset += limit


def merge_unique(existing, new):
    """Append items from `new` whose URL isn't already in `existing`."""
    seen = {i["url"].split("?")[0] for i in existing}
    for item in new:
        key = item["url"].split("?")[0]
        if key not in seen:
            seen.add(key)
            existing.append(item)
    return existing


def fetch_sponsored(session, bioguide_id, refresh):
    """Load one member's sponsored items from the saved file, or download them."""
    cache = RAW_DIR / f"{bioguide_id}.json"
    if cache.exists() and not refresh:
        # Reuse the saved file and drop any repeated items.
        result = json.loads(cache.read_text(encoding="utf-8"))
        result["items"] = merge_unique([], result["items"])
    else:
        # Download every page and drop any repeats.
        items, total = fetch_all_pages(session, bioguide_id, 250)
        result = {"bioguide_id": bioguide_id, "expected_count": total,
                  "items": merge_unique([], items)}

    # The API's ordering isn't stable between page requests, so an item can be
    # repeated across a page boundary while another is skipped. Re-page with
    # different sizes (moving the boundaries) and merge until the count matches.
    if len(result["items"]) < result["expected_count"] and not result.get("gap_filled"):
        for limit in (100, 200, 150, 50):
            items, _ = fetch_all_pages(session, bioguide_id, limit)
            merge_unique(result["items"], items)
            if len(result["items"]) >= result["expected_count"]:
                break
        result["gap_filled"] = True

    # Save the combined list so the next run can skip this member.
    cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def to_row(item, member):
    """Turn one sponsored item into a bill row or an amendment row."""
    # Shared facts: dates, the sponsor, the latest action, and the API link.
    latest = item.get("latestAction") or {}
    row = {
        "congress": item.get("congress"),
        "introduced_date": item.get("introducedDate"),
        "sponsor_bioguide_id": member["bioguide_id"],
        "sponsor_name": member["name"],
        "sponsor_party": member["party_code"],
        "sponsor_state": member["state_code"],
        "latest_action_date": latest.get("actionDate"),
        "latest_action": latest.get("text"),
        "api_url": (item.get("url") or "").split("?")[0],
    }
    # An amendment has a number and no title. A bill or resolution has a title.
    if item.get("amendmentNumber"):
        # House and Senate amendments are numbered separately; the type
        # (hamdt / samdt / suamdt) only appears in the URL
        amdt_type = row["api_url"].rstrip("/").split("/")[-2]
        return "amendment", {"amendment_id": f"{item['congress']}-{amdt_type}-{item['amendmentNumber']}",
                             "amendment_type": amdt_type,
                             "amendment_number": item["amendmentNumber"], **row}
    bill_type = (item.get("type") or "").lower()
    return "bill", {"bill_id": f"{item['congress']}-{bill_type}-{item.get('number')}",
                    "bill_type": bill_type, "bill_number": item.get("number"),
                    "title": item.get("title"),
                    "policy_area": (item.get("policyArea") or {}).get("name"), **row}


def main():
    """Download sponsored bills for every member and write two CSV files."""
    # Read which members file to use, and whether to ignore saved copies.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--congress", type=int, default=119,
                        help="which members file to use (data/members_N.csv)")
    parser.add_argument("--refresh", action="store_true", help="re-download cached responses")
    args = parser.parse_args()

    # Stop if the member list has not been downloaded yet.
    members_path = DATA_DIR / f"members_{args.congress}.csv"
    if not members_path.exists():
        sys.exit(f"{members_path} not found - run scripts/fetch_members.py first.")
    members = (pd.read_csv(members_path, dtype=str)
               .drop_duplicates("bioguide_id").to_dict("records"))

    # Send the API key with every request. Download a few members at once.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.params = {"api_key": load_api_key(), "format": "json"}

    print(f"Fetching sponsored legislation for {len(members)} members...")
    done = 0

    def fetch(member):
        """Download one member's bills and print progress every 50 people."""
        nonlocal done
        result = fetch_sponsored(session, member["bioguide_id"], args.refresh)
        done += 1
        if done % 50 == 0 or done == len(members):
            print(f"  {done}/{len(members)} members")
        return member, result

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(fetch, members))

    # Split each item into a bill or an amendment. Note anyone still short.
    bills, amendments, mismatches = [], [], []
    for member, result in results:
        if len(result["items"]) < result["expected_count"]:
            mismatches.append((member["name"], len(result["items"]), result["expected_count"]))
        for item in result["items"]:
            kind, row = to_row(item, member)
            (bills if kind == "bill" else amendments).append(row)

    # Drop repeats, put the newest first, and write the two files.
    bills_df = (pd.DataFrame(bills).drop_duplicates("bill_id")
                .sort_values(["congress", "introduced_date"], ascending=False))
    amdt_df = (pd.DataFrame(amendments).drop_duplicates("amendment_id")
               .sort_values(["congress", "introduced_date"], ascending=False))

    bills_path = DATA_DIR / f"sponsored_bills_{args.congress}.csv"
    amdt_path = DATA_DIR / f"sponsored_amendments_{args.congress}.csv"
    bills_df.to_csv(bills_path, index=False, encoding="utf-8")
    amdt_df.to_csv(amdt_path, index=False, encoding="utf-8")

    # Report what was saved, and warn if some items are still missing.
    print(f"\nSaved {len(bills_df):,} bills/resolutions -> {bills_path.relative_to(PROJECT_ROOT)}")
    print(f"Saved {len(amdt_df):,} amendments         -> {amdt_path.relative_to(PROJECT_ROOT)}")
    if len(bills) != len(bills_df) or len(amendments) != len(amdt_df):
        print(f"  (dropped {len(bills) - len(bills_df)} duplicate bills, "
              f"{len(amendments) - len(amdt_df)} duplicate amendments)")
    if mismatches:
        missing = sum(expected - got for _, got, expected in mismatches)
        print(f"\nWarning: {missing} items still missing across {len(mismatches)} members "
              "(the API reported more than it returned):")
        for name, got, expected in mismatches[:10]:
            print(f"  {name}: got {got} unique, expected {expected}")

    print("\nBills by congress (most recent 6):")
    print(bills_df["congress"].value_counts().sort_index(ascending=False).head(6).to_string())
    print("\nBills by type:")
    print(bills_df["bill_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
