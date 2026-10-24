# Topic Scout app

The topic-scout skill as an app on your phone. You type a topic, and a small server runs the pipeline and returns a cited brief: news, X, Reddit, Hacker News, long-form and YouTube.

```
 Phone (installed web app) ──HTTPS──▶ server.py on your Mac (or a cloud host)
                                         1. plan queries              (Claude, low effort)
                                         2. in parallel:
                                            · web research            (Claude + web search/fetch)
                                            · Reddit                  (reddit_scout.py: RSS, or API if keyed)
                                            · Hacker News             (Algolia API)
                                         3. write the brief           (Claude)
```

Briefs are saved as JSON in `data/briefs/`. One brief runs at a time and the rest queue, because Reddit RSS is rate-limited per IP.

## Set up on your Mac (about 10 minutes)

1. **API key.** Create a key at <https://console.anthropic.com/settings/keys> and add credit under Billing.
2. **Config.** In this folder:
   ```bash
   cp .env.example .env
   open -e .env      # paste ANTHROPIC_API_KEY, and set APP_TOKEN to the output of: openssl rand -hex 16
   ```
3. **Start it.**
   ```bash
   bash run.sh
   ```
   The first run installs `uv` and Python 3.12. Check it at <http://127.0.0.1:8787>.
4. **Reach it from your phone with Tailscale** (free, private, works on mobile data):
   - Install Tailscale on the Mac (<https://tailscale.com/download/mac>) and on your phone (App Store / Play Store). Sign in to the same account on both.
   - On the Mac, run `tailscale serve --bg 8787`. It prints a URL like `https://pranavs-macbook.tailXXXX.ts.net`. If it asks you to enable HTTPS certificates, click the link it gives and enable them.
5. **Install on the phone.** Open that URL with Tailscale switched on.
   - **iPhone:** in Safari, tap Share, then *Add to Home Screen*.
   - **Android:** in Chrome, tap ⋮, then *Install app* (or *Add to Home screen*).
   Open the app and paste your `APP_TOKEN` once.
6. **Optional: keep it running.** `bash mac-autostart.sh` starts the server at login and restarts it if it crashes (`bash mac-autostart.sh off` undoes it). Run `tailscale serve --bg 8787` once and it persists. The Mac has to be awake: `run.sh` blocks idle sleep, but closing the lid on battery still sleeps it.

## Reddit

- **Without API keys** (today), Reddit uses logged-out RSS from your Mac's home connection at about 1 request a minute. Because it runs alongside the web research, it sets the total time: roughly 5 minutes at quick depth, 15 at standard and 35 at deep. Turn off *Include Reddit* in the app for a fast run.
- **With API keys** (once Reddit approves your registration), add `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` to `.env` and restart. Reddit then runs in seconds, includes scores, and works from a cloud host too.
- Reddit is not reachable from cloud servers without keys. If a run can't reach it, the brief says so under Coverage and never makes up Reddit sentiment.

## Move to the cloud later (optional)

Once you have Reddit API keys, the same code runs on any Docker host, so your Mac can sleep.

- **Render:** New → Web Service → connect a GitHub repo holding this folder → Docker. Add the `.env` values as environment variables. Add a persistent disk mounted at `/data` (from about $7/month on the Starter plan), or briefs disappear on each redeploy.
- **Railway / Fly.io:** same Dockerfile, same environment variables, with a volume at `/data`.

The phone app then lives at the host's HTTPS URL. Install it the same way.

## Cost

Claude API usage with the default model, `claude-opus-5-5` ($4 / $20 per million input/output tokens, plus $10 per 1,000 web searches):

| Depth | Typical cost | Time without Reddit |
|---|---|---|
| Quick | ~$0.30 | 3–5 min |
| Standard | ~$1–1.50 | 5–8 min |
| Deep | ~$3–4 | 10–15 min |

Each brief shows its actual token count and estimated cost at the bottom. For about half the cost, set `TOPIC_SCOUT_MODEL=claude-sonnet-5-5` in `.env`.

## Files

| File | What it does |
|---|---|
| `server.py` | API (`/api/briefs`) and serves the app; bearer-token auth |
| `pipeline.py` | plan → research + Reddit + HN → write |
| `prompts.py` | prompts condensed from the topic-scout SKILL.md |
| `reddit_scout.py` | the same Reddit fetcher the skill uses |
| `static/` | the installable web app (manifest, service worker, icons) |
| `run.sh`, `mac-autostart.sh` | run on a Mac, start at login |
| `Dockerfile` | cloud hosting |

## Security

- Every API call needs `APP_TOKEN`. Use a long random one and don't share it.
- Over Tailscale, only your own devices can reach the server, because it binds to `127.0.0.1` and `tailscale serve` proxies to it. Don't use `tailscale funnel` unless you want it on the public internet.
- `.env` holds your keys and is git-ignored. Never paste it into chat.
