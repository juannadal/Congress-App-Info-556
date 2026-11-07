"""Download a portrait for every member in data/members_{congress}.csv.

Sources, in order:
  1. Congress.gov official portrait (the image_url from the member data).
     With --full, also saves the original high-resolution file when one exists
     (older portraits only exist at the small size).
  2. Wikimedia Commons, via the member's Wikidata image (P18), for members
     Congress.gov has no portrait for.

Downloads run one at a time with a pause between requests.

Outputs:
  data/images/members/{bioguide_id}.jpg          portrait (~200px wide from Congress.gov)
  data/images/members_full/{bioguide_id}.jpg     originals (only with --full)
  data/member_images_{congress}.csv              source, attribution, size for each image

Usage:
  python scripts/fetch_member_images.py
  python scripts/fetch_member_images.py --full     # also get high-resolution originals
  python scripts/fetch_member_images.py --refresh  # re-download existing files
"""

import argparse
import io
import json
import sys
import time

import pandas as pd
import requests
from PIL import Image

from fetch_members import DATA_DIR, PROJECT_ROOT
from fetch_wikipedia import WIKIDATA_SPARQL, user_agent

IMAGE_DIR = DATA_DIR / "images" / "members"
FULL_DIR = DATA_DIR / "images" / "members_full"
RAW_MEMBERS = DATA_DIR / "raw" / "members"


def download(session, url, max_attempts=5):
    """Return image bytes, or None if the image doesn't exist."""
    for attempt in range(max_attempts):
        wait = 5 * 2 ** attempt
        try:
            resp = session.get(url, timeout=60)
        except (requests.Timeout, requests.ConnectionError) as e:
            # The connection failed. Wait and try again.
            print(f"    {type(e).__name__}, waiting {wait}s")
            time.sleep(wait)
            continue
        # No picture at this address.
        if resp.status_code == 404:
            return None
        # The server is busy. Wait and try again.
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = max(int(resp.headers.get("Retry-After", 0) or 0), wait)
            print(f"    HTTP {resp.status_code}, waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        # Reject a reply that is not an image.
        if not resp.headers.get("Content-Type", "").startswith("image/"):
            raise RuntimeError(f"not an image ({resp.headers.get('Content-Type')}): {url}")
        return resp.content
    # Stop after several failed tries.
    raise RuntimeError(f"Giving up on {url} after {max_attempts} attempts")


def save_as_jpeg(content, path):
    """Save image bytes as JPEG and return (width, height)."""
    img = Image.open(io.BytesIO(content))
    if img.format == "JPEG":
        path.write_bytes(content)
    else:
        img.convert("RGB").save(path, "JPEG", quality=92)
    return img.size


def image_size(path):
    """Read the width and height of a saved image."""
    with Image.open(path) as img:
        return img.size


def congress_attribution(bioguide_id):
    """Read the photo credit from the saved member record, if there is one."""
    cache = RAW_MEMBERS / f"{bioguide_id}.json"
    if cache.exists():
        detail = json.loads(cache.read_text(encoding="utf-8"))
        return (detail.get("depiction") or {}).get("attribution")
    return None


# Find a Commons photo for members who have no Congress.gov portrait.
def commons_images(session, bioguide_ids):
    """Map bioguide ID -> Wikimedia Commons file name, via Wikidata P18."""
    if not bioguide_ids:
        return {}
    # Ask Wikidata for the photo file tied to each bioguide ID.
    query = """SELECT ?bioguide ?image WHERE {
      VALUES ?bioguide { %s }
      ?item wdt:P1157 ?bioguide ; wdt:P18 ?image .
    }""" % " ".join(f'"{b}"' for b in bioguide_ids)
    resp = session.post(WIKIDATA_SPARQL, data={"query": query, "format": "json"},
                        headers={"Accept": "application/sparql-results+json"}, timeout=120)
    resp.raise_for_status()
    # Keep one file name per member.
    result = {}
    for row in resp.json()["results"]["bindings"]:
        file_name = requests.utils.unquote(row["image"]["value"].rsplit("/", 1)[1])
        result.setdefault(row["bioguide"]["value"], file_name)
    return result


def main():
    """Download a portrait for every member and write a list of the files."""
    # Read the Congress, whether to get large originals, the pause, and whether to ignore saved files.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--congress", type=int, default=119)
    parser.add_argument("--full", action="store_true", help="also download high-resolution originals")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between downloads")
    parser.add_argument("--refresh", action="store_true", help="re-download existing images")
    args = parser.parse_args()

    # Stop if the member list has not been downloaded yet.
    members_path = DATA_DIR / f"members_{args.congress}.csv"
    if not members_path.exists():
        sys.exit(f"{members_path} not found - run scripts/fetch_members.py first.")
    members = pd.read_csv(members_path, dtype=str).drop_duplicates("bioguide_id")

    # Make the image folders and tell the sites who is calling.
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    if args.full:
        FULL_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = user_agent()

    # Try the official Congress.gov portrait first.
    records = []
    no_congress_image = []
    todo = members.to_dict("records")
    print(f"Downloading Congress.gov portraits for {len(todo)} members...")

    for n, member in enumerate(todo, 1):
        bioguide_id, url = member["bioguide_id"], member.get("image_url")
        # No Congress.gov photo. Try Wikimedia later.
        if not isinstance(url, str) or not url:
            no_congress_image.append(member)
            continue

        path = IMAGE_DIR / f"{bioguide_id}.jpg"
        record = {"bioguide_id": bioguide_id, "name": member["name"], "source": "congress.gov",
                  "source_url": url, "attribution": congress_attribution(bioguide_id),
                  "file_path": path.relative_to(PROJECT_ROOT).as_posix()}

        # Skip the download when this portrait is already saved.
        if not path.exists() or args.refresh:
            if n % 25 == 0 or n == len(todo):
                print(f"  [{n}/{len(todo)}]")
            content = download(session, url)
            time.sleep(args.delay)
            if content is None:
                # The link is dead. Try Wikimedia later.
                print(f"  404 for {member['name']}: {url}")
                no_congress_image.append(member)
                continue
            save_as_jpeg(content, path)
        record["width"], record["height"] = image_size(path)

        if args.full:
            # The small link has "_200" in the name. Without that, the original may exist.
            full_path = FULL_DIR / f"{bioguide_id}.jpg"
            if not full_path.exists() or args.refresh:
                content = download(session, url.replace("_200.", "."))
                time.sleep(args.delay)
                if content is not None:
                    save_as_jpeg(content, full_path)
            if full_path.exists():
                w, h = image_size(full_path)
                # Older portraits have no larger version; don't keep duplicates
                if (w, h) == (record["width"], record["height"]):
                    full_path.unlink()
                else:
                    record["full_file_path"] = full_path.relative_to(PROJECT_ROOT).as_posix()
                    record["full_width"], record["full_height"] = w, h
        records.append(record)

    # For anyone still missing a photo, try Wikimedia Commons.
    missing = []
    if no_congress_image:
        print(f"\nLooking up Wikimedia Commons images for {len(no_congress_image)} members...")
        commons = commons_images(session, [m["bioguide_id"] for m in no_congress_image])
        for member in no_congress_image:
            bioguide_id = member["bioguide_id"]
            # No Commons photo either. Report them at the end.
            if bioguide_id not in commons:
                missing.append(member["name"])
                continue
            file_name = commons[bioguide_id]
            # Ask Commons for a 400-pixel-wide copy of that file.
            url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{requests.utils.quote(file_name)}?width=400"
            path = IMAGE_DIR / f"{bioguide_id}.jpg"
            # Skip the download when this portrait is already saved.
            if not path.exists() or args.refresh:
                print(f"  {member['name']} -> {file_name}")
                content = download(session, url)
                time.sleep(args.delay)
                if content is None:
                    missing.append(member["name"])
                    continue
                save_as_jpeg(content, path)
            width, height = image_size(path)
            records.append({
                "bioguide_id": bioguide_id, "name": member["name"], "source": "wikimedia_commons",
                "source_url": url,
                "attribution": f"Wikimedia Commons: https://commons.wikimedia.org/wiki/File:{file_name.replace(' ', '_')} (see page for license)",
                "file_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "width": width, "height": height,
            })

    # Write the list of portraits and say who is still missing.
    df = pd.DataFrame(records)
    manifest = DATA_DIR / f"member_images_{args.congress}.csv"
    df.to_csv(manifest, index=False, encoding="utf-8")

    print(f"\nSaved {len(df)}/{len(members)} portraits to {IMAGE_DIR.relative_to(PROJECT_ROOT)}")
    print(df["source"].value_counts().to_string())
    if args.full and "full_file_path" in df:
        print(f"High-resolution originals: {df['full_file_path'].notna().sum()} "
              f"in {FULL_DIR.relative_to(PROJECT_ROOT)}")
    print(f"Manifest: {manifest.relative_to(PROJECT_ROOT)}")
    if missing:
        print(f"\nNo image found for {len(missing)}: {', '.join(missing)}")


if __name__ == "__main__":
    main()
