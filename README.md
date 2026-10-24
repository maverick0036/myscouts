# myscouts

Topic Scout: type a topic, get a cited brief of what the web is saying (news, X, Hacker News, Substack, YouTube).

- **`index.html`** is the browser version, served by GitHub Pages at https://maverick0036.github.io/myscouts/. It has two modes:
  - **Free**: Gemini's free tier with Google Search, plus Hacker News. Needs a free key from aistudio.google.com/apikey. Daily limits apply, and Google may use free-tier requests to improve its products.
  - **Claude**: Claude Opus 5.5 with web search and fetch. Deeper, about $0.30 to $3 a brief.
  Both are people-first: consultancy, corporate and press-release sources are excluded. Keys stay in your browser.
- **`index.src.html`** is its readable source. `index.html` is the same page with the Anthropic JS SDK (0.133.0), CSS and icon inlined.
- **`mac-app/`** is the full version with Reddit: a small Python server you run on your Mac and reach from your phone over Tailscale. Setup is in `mac-app/README.md`.

The repo holds no keys. Never commit `.env`.
