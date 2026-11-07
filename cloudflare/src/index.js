// Cloudflare Worker in front of the Streamlit app, which runs as a Cloudflare Container
// (the Docker image built from ../Dockerfile). Every visitor goes to the same container instance:
// Streamlit serves many browser sessions from one server, and one shared instance keeps the
// paid-call caps in retrieval/deploy.py meaningful. The container sleeps after SLEEP_AFTER without
// visitors, so the first visit after a quiet spell waits while it starts (cold start).
import { Container } from "@cloudflare/containers";

const SLEEP_AFTER = "15m";

// This class is the app container. Its name matches cloudflare/wrangler.jsonc.
export class CongressApp extends Container {
  defaultPort = 8080; // Streamlit listens here (see the Dockerfile CMD)
  sleepAfter = SLEEP_AFTER;

  constructor(ctx, env) {
    super(ctx, env);
    // Worker secrets (set with `wrangler secret put`) are passed to the container as environment
    // variables, where retrieval/deploy.py's get_secret() reads them. Unset ones are left out.
    const names = ["ANTHROPIC_API_KEY", "XAI_API_KEY", "XAI_MODEL", "OVERVIEW_ENABLED",
                   "PAID_CALLS_PER_SESSION", "PAID_CALLS_PER_DAY"];
    this.envVars = Object.fromEntries(names.filter((n) => env[n]).map((n) => [n, String(env[n])]));
  }
}

export default {
  async fetch(request, env) {
    // fetch() forwards plain HTTP and Streamlit's WebSocket, starting the container if it is asleep
    // "main" is the one shared copy of the app. Every visitor uses that same copy.
    return env.CONGRESS_APP.getByName("main").fetch(request);
  },
};
