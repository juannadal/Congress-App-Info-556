# Putting the app on the web (Cloudflare)

The public site runs the same Streamlit app as a **Cloudflare Container** (the Docker image from `Dockerfile`), with a
small **Cloudflare Worker** in front (`cloudflare/`) that sends visitors to it. Your domain, DNS, and the app all live
in one Cloudflare account. You deploy from your Mac with `wrangler deploy`.

## What is different on the public site

The image sets `PUBLIC_DEMO=1` (see `retrieval/deploy.py`), which:

- hides the **Label passages** page (it is not listed, and opening its address only shows a notice), and the
  "Add to queries.csv" box in the sidebar
- stops writing searches to `eval/query_log.csv`
- caps **new** paid AI calls (the re-ranker and the Grok overview share the cap): 10 per visitor session and
  200 per day for the whole site. Answers already cached are free and don't count. The daily count starts over when
  the container restarts, so the key spending limits below are the real ceiling.

The dense index and the MiniLM model are built into the image during the Docker build, so the site needs no index
files from your Mac.

**Cold starts:** the container goes to sleep after 15 minutes with no visitors (`SLEEP_AFTER` in
`cloudflare/src/index.js`), so you only pay while people use it. The first visitor after that waits while it starts
and loads the indexes (expect roughly half a minute; not yet measured). Open the site yourself a minute before a demo.

## 1. Set spending limits first

- Anthropic console: make a new key just for the website and give it a monthly spend limit (for example $10).
- xAI console: same for a new Grok key.

## 2. Merge the pull requests

On GitHub, merge PR #2 (AI overview) first, then PR #1 (this deploy setup). Then on your Mac:

    cd ".../INFO 556 - Text Retrieval and Web Search/Project"
    git pull

## 3. One-time setup on your Mac

1. Cloudflare dashboard > **Workers & Pages** > **Plans**: switch to **Workers Paid** ($5/month). Containers need it.
2. Install and start **Docker Desktop** (Wrangler uses it to build the image).
3. In Terminal:

       cd cloudflare
       npm install
       npx wrangler login

## 4. Add the keys as secrets and deploy

From the `cloudflare` folder:

    npx wrangler secret put ANTHROPIC_API_KEY     # paste the website key when asked
    npx wrangler secret put XAI_API_KEY
    npx wrangler deploy

If `secret put` asks whether to create the Worker `congress-search`, say yes. The first deploy builds the image for
Linux (about 10-20 minutes on a Mac, since PyTorch is installed and 18,434 passages are embedded) and uploads it.
When it finishes, Wrangler prints the address, like `https://congress-search.<your-subdomain>.workers.dev`. The
container can take a few more minutes to roll out before the first visit works.

Optional settings, also with `npx wrangler secret put NAME`: `XAI_MODEL` (another Grok model), `OVERVIEW_ENABLED`
(`0` turns the AI overview off), `PAID_CALLS_PER_SESSION`, `PAID_CALLS_PER_DAY`. A running container picks up changed
settings the next time it starts.

## 5. Use your own domain (optional)

Cloudflare dashboard > **Workers & Pages** > `congress-search` > **Settings** > **Domains & Routes** > **Add** >
**Custom domain**, and enter for example `congress.yourdomain.com` (the domain must already be on your Cloudflare
account). Cloudflare creates the DNS record and certificate itself.

## Updating the site

After changing the app, run `npx wrangler deploy` again from `cloudflare/`. Docker reuses the cached layers, so only
the changed parts rebuild. To watch logs: `npx wrangler tail`, or the Worker's **Logs** tab in the dashboard.

## Taking it down

`npx wrangler delete` from `cloudflare/`, then switch back to the free Workers plan if nothing else needs it.

## Cost

Workers Paid is $5 a month and includes some container time. Beyond that, the `standard-1` instance (1/2 vCPU,
4 GiB) costs about 4 cents per hour while awake (memory and disk are billed while it runs; CPU only when busy), and
nothing while asleep. AI calls are paid separately to Anthropic and xAI and limited by the caps above. Prices from
Cloudflare's Containers pricing page as of November 2026.

## Running the image on your Mac (optional)

    docker build -t congress-search .
    docker run -p 8080:8080 -e ANTHROPIC_API_KEY=... -e XAI_API_KEY=... congress-search

Then open http://localhost:8080. Normal local use (`streamlit run app.py`) is unchanged: no caps, labeling page
shown, keys read from `~/.info556/.env`.
