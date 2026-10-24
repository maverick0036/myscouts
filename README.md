# myscouts

Topic Scout: type a topic, get a cited brief of what the web is saying (news, X, Hacker News, Substack, YouTube).

- **`index.html`** is the browser version, served by GitHub Pages. Open the Pages link on your phone, paste your Claude API key once (it stays in that browser), and use Add to Home Screen. It has no Reddit, because browsers can't reach it.
- **`index.src.html`** is its readable source. `index.html` is the same page with the Anthropic JS SDK (0.133.0), CSS and icon inlined.
- **`mac-app/`** is the full version with Reddit: a small Python server you run on your Mac and reach from your phone over Tailscale. Setup is in `mac-app/README.md`.

The repo holds no keys. Never commit `.env`.
