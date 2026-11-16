# Data

The processed data for the project: the 555 members of the 119th Congress, their Wikipedia biographies, the
18,434 passages that the search methods index, and member portraits. All files were made by the scripts in
`scripts/` (see [How the files were made](#how-the-files-were-made)). The raw API responses those scripts cache in
`data/raw/` are not included, because they are large and can be downloaded again.

The `119` in each file name is the Congress number. The scripts take `--congress` to build the same files for
another Congress.

## Files at a glance

| File | Rows | What it is | Made by | Used by |
|---|---|---|---|---|
| `passages_119.jsonl` | 18,434 | **The search corpus**: one row per passage, with member metadata | `chunk_wikipedia.py` | The app, all four search methods, and the evaluation |
| `passages_119.csv` | 18,434 | The same passages as CSV, for opening in Excel | `chunk_wikipedia.py` | People (not read by code) |
| `wikipedia_articles_119.jsonl` | 555 | One full Wikipedia article per member | `fetch_wikipedia.py` | `chunk_wikipedia.py` |
| `wikipedia_articles_119.csv` | 555 | The same articles without the `text` column | `fetch_wikipedia.py` | People (not read by code) |
| `members_119.csv` | 555 | One row per member: chamber, party, state, terms, contact info | `fetch_members.py` | The other `fetch_*` scripts |
| `members_119.json` | 555 | The same rows as JSON | `fetch_members.py` | People and other tools |
| `member_images_119.csv` | 555 | Source and attribution for each portrait | `fetch_member_images.py` | Records image credits |
| `images/members/{bioguide_id}.jpg` | 555 | Member portraits (about 200 px wide) | `fetch_member_images.py` | The app's result cards |
| `sponsored_bills_119.csv` | 92,217 | Bills and resolutions sponsored by each member | `fetch_sponsored_bills.py` | Not used by search (see below) |
| `sponsored_amendments_119.csv` | 35,984 | Amendments sponsored by each member | `fetch_sponsored_bills.py` | Not used by search (see below) |

All text files are UTF-8. The key that links every file is **`bioguide_id`**, the member's official Congress
identifier (for example `M001212`).

**Coverage:** 555 members (451 House, 104 Senate; 283 Republican, 270 Democratic, 2 Independent). Every member has
a Wikipedia article, at least one passage, and a portrait. The list includes everyone who served in the 119th
Congress, so 16 members who have since left office are included (`current_member` is `False`). The Wikipedia articles
were downloaded on 2026-09-15. Wikipedia
articles are pinned by `revision_id`, so the exact article versions can be looked up later.

## Column reference

### `passages_119.jsonl` / `passages_119.csv` (the search corpus)

| Column | Meaning |
|---|---|
| `passage_id` | Unique ID: `{bioguide_id}-{passage_index}`, for example `M001212-000` |
| `bioguide_id`, `name` | The member the passage is about |
| `chamber` | `House` or `Senate` (a search filter) |
| `party` | `Republican`, `Democratic`, or `Independent` (a search filter) |
| `state_code` | Two-letter state or territory code (a search filter) |
| `section` | Section path in the article, for example `U.S. Senate > Committee assignments` |
| `passage_index` | Position of the passage within the member's article, starting at 0 |
| `word_count` | Words in `text` (average 71, maximum 180) |
| `token_count` | MiniLM word pieces in `text_with_context` (maximum 256, the model's input limit) |
| `text` | The passage. **This is what BM25 and dense search index.** |
| `text_with_context` | `text` with the member's name and section in front, since many passages only say "He" or "She". Kept for experiments; the reported results use `text`. |
| `wikipedia_url` | Link to the article |
| `revision_id` | Wikipedia revision the passage came from |

**How passages were made** (details in `scripts/chunk_wikipedia.py`): non-prose sections are dropped (References,
External links, See also, Notes, Further reading, Electoral history). Each remaining paragraph becomes a passage.
Paragraphs under 40 words are merged with a neighbor in the same section, lists are joined into one passage, and
passages over 180 words or 256 word pieces are split at sentence boundaries. Passages never cross section boundaries.

### `wikipedia_articles_119.jsonl` / `.csv`

| Column | Meaning |
|---|---|
| `bioguide_id`, `name`, `chamber`, `state_code`, `party` | Member metadata, copied from `members_119.csv` |
| `wikidata_id` | The member's Wikidata item (for example `Q63198048`), found through Wikidata property P1157 (US Congress Bio ID). Articles are matched by this ID, not by name. |
| `wikipedia_title`, `wikipedia_url`, `page_id` | The English Wikipedia article |
| `revision_id` | The exact article version downloaded |
| `fetched_at` | Download time (UTC) |
| `word_count` | Words in the article (1.41 million in total) |
| `text` | Full plain-text article, with `== Section ==` headings (JSONL only) |

### `members_119.csv` / `members_119.json`

From the Congress.gov API (`/v3/member`). One row per member per chamber served in the 119th Congress.

| Column | Meaning |
|---|---|
| `bioguide_id`, `name`, `first_name`, `last_name` | Identity |
| `chamber`, `member_type` | `House`/`Senate` and `Representative`/`Senator`/`Delegate`/`Resident Commissioner` |
| `state`, `state_code`, `district` | Where they represent (`district` is blank for senators) |
| `party`, `party_code` | Party name and letter (`R`, `D`, `I`) |
| `term_start_year`, `term_end_year`, `current_member` | Term in this chamber; `term_end_year` is blank while serving |
| `birth_year` | Year of birth |
| `website`, `office_address`, `phone` | Official contact information |
| `sponsored_bills`, `cosponsored_bills` | Career counts reported by Congress.gov |
| `image_url` | Official portrait URL |
| `api_url` | Congress.gov API record |

### `member_images_119.csv`

| Column | Meaning |
|---|---|
| `bioguide_id`, `name` | The member |
| `source` | `congress.gov` (553 official portraits) or `wikimedia_commons` (2 members with no official portrait) |
| `source_url` | Where the image was downloaded from |
| `attribution` | Credit line required by the source (for example "Image courtesy of the Member") |
| `file_path` | Local file, `data/images/members/{bioguide_id}.jpg` |
| `width`, `height` | Image size in pixels |

### `sponsored_bills_119.csv` and `sponsored_amendments_119.csv`

From the Congress.gov API (`/v3/member/{id}/sponsored-legislation`). These cover each member's **whole career**
(Congresses 94–119), not just the 119th, so there are many more rows than members.

| Column | Meaning |
|---|---|
| `bill_id` / `amendment_id` | `{congress}-{type}-{number}`, for example `119-hr-10331` |
| `bill_type` / `amendment_type`, `bill_number` / `amendment_number` | Type (`hr`, `s`, `hres`, `samdt`, ...) and number |
| `title`, `policy_area` | Bill title and Congress.gov policy area (bills only; this endpoint gives amendments no title) |
| `congress`, `introduced_date` | When it was introduced |
| `sponsor_bioguide_id`, `sponsor_name`, `sponsor_party`, `sponsor_state` | The sponsoring member |
| `latest_action_date`, `latest_action` | Most recent action on it |
| `api_url` | Congress.gov API record |

**Why these are here but not searched:** they were collected during data gathering as extra information about each
member. The search corpus is limited to Wikipedia biographies so that all four methods are compared on one kind of
text. These files are kept as supporting data and for future work, such as searching a member's legislation.

## How the files were made

Run from the project root, in this order. Each script caches API responses in `data/raw/` and skips files it already
has, so a rerun only downloads what is missing (`--refresh` downloads everything again).

```bash
python scripts/fetch_members.py          # 1. members_119.csv/.json             (needs CONGRESS_API_KEY)
python scripts/fetch_wikipedia.py        # 2. wikipedia_articles_119.jsonl/.csv
python scripts/chunk_wikipedia.py        # 3. passages_119.jsonl/.csv
python scripts/fetch_member_images.py    # 4. images/members/ and member_images_119.csv
python scripts/fetch_sponsored_bills.py  # 5. sponsored_*_119.csv                (needs CONGRESS_API_KEY)
```

- **Congress.gov API key:** free from [api.data.gov/signup](https://api.data.gov/signup/). Put
  `CONGRESS_API_KEY=...` in the environment, in a `.env` file in the project root, or in `congress-api/.env` (see
  `congress-api/.env.example`).
- **Wikimedia contact (optional):** Wikimedia asks scripts to identify themselves. Set `WIKIMEDIA_CONTACT` to an email
  or URL, and it is added to the User-Agent.
- **Steps 2–4 need no key.**

**Warning:** rerunning steps 1–3 downloads the *current* Congress and Wikipedia. Members change and articles get
edited, so the passages would change too, and the relevance labels in `eval/` (which refer to `passage_id`s) would no
longer match. To reproduce the reported results, use the files as committed.

## Sources and licenses

- **Congress.gov API** (Library of Congress): member and legislation data. US government work, public domain.
- **Wikipedia** text: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Each passage keeps its article
  URL and revision ID for attribution.
- **Portraits:** official Congress.gov portraits ("courtesy of the Member") and two Wikimedia Commons images; the
  credit for each is in `member_images_119.csv`.
