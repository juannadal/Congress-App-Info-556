#!/usr/bin/env bash
# Hello World for the Congress.gov API, using curl.
#
# Calls GET /v3/member/congress/{congress}/{state} and lists the members
# of Congress for one state.
#
# Usage:
#   ./congress_hello.sh              # Arizona, 119th Congress
#   ./congress_hello.sh CA           # California, 119th Congress
#   ./congress_hello.sh TX 118       # Texas, 118th Congress
#
# The API key is read from a .env file next to this script
# (copy .env.example to .env). Without one, the shared DEMO_KEY is used,
# which is limited to a handful of requests per hour.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
fi

API_KEY="${CONGRESS_API_KEY:-DEMO_KEY}"
STATE="$(printf '%s' "${1:-AZ}" | tr '[:lower:]' '[:upper:]')"
CONGRESS="${2:-119}"

if [[ "$API_KEY" == "DEMO_KEY" ]]; then
  echo "(No CONGRESS_API_KEY in .env - using the rate-limited DEMO_KEY)"
fi

# --- Call the API -----------------------------------------------------------
# Ask for the members from this state in this Congress.
URL="https://api.congress.gov/v3/member/congress/$CONGRESS/$STATE?format=json&limit=250"
echo "Fetching members for $STATE in the ${CONGRESS}th Congress..."

# Call the API. Keep the HTTP status code on the last line of the reply.
RESPONSE="$(curl -sS -w '\n%{http_code}' "$URL&api_key=$API_KEY")"
# Take that status code off the JSON so we can check it.
HTTP_STATUS="${RESPONSE##*$'\n'}"
BODY="${RESPONSE%$'\n'*}"

# Check that the call succeeded. Anything other than 200 is a failure.
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "API request failed (HTTP $HTTP_STATUS):" >&2
  echo "$BODY" >&2
  exit 1
fi

# --- Print the results ------------------------------------------------------
if ! command -v python >/dev/null 2>&1; then
  echo "$BODY"   # no Python: show the raw JSON
  exit 0
fi

export BODY
export PYTHONUTF8=1   # print accented names (e.g. "Raúl") correctly on Windows
python - <<'PY'
import json, os

members = json.loads(os.environ["BODY"]).get("members", [])
# Check that the reply actually lists members.
if not members:
    print("\nNo members found - check the state code (e.g. AZ) and Congress number.")
    raise SystemExit(1)

# Senate if the latest term says Senate. Otherwise the House.
def chamber(m):
    return "Senate" if m["terms"]["item"][-1].get("chamber") == "Senate" else "House"

print()
print(f"Hello, Congress! Found {len(members)} members:")
print()
print(f"{'Name':<30} {'Party':<12} {'Chamber':<8} District")
print("-" * 60)

# Senators first, then House members by district
for m in sorted(members, key=lambda m: (chamber(m) != "Senate", m.get("district") or 0)):
    district = m.get("district")
    print(f"{m['name']:<30} {m.get('partyName', ''):<12} {chamber(m):<8} "
          f"{district if district is not None else '-'}")
PY
