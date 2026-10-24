#!/usr/bin/env python3
"""topic-scout Reddit fetcher.

  python3 reddit_scout.py "<query>" [--subs a,b] [--t month] [--sort relevance]
                          [--limit 15] [--comments 8] [--threads 12] [--exact]

JSON to stdout, progress to stderr.

Source: the official OAuth API (app-only client_credentials) when REDDIT_CLIENT_ID and
REDDIT_CLIENT_SECRET are set (env, a .env next to this script, or
~/.config/topic-scout/reddit.env). Otherwise, or if the token call fails, it uses the
public RSS feeds, which work logged-out (the .json endpoints are blocked) but have no
scores, a ~1 request/min limit, and no comment counts until a thread is opened.
"""
import argparse, base64, html, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "script:topic-scout:0.3 (personal research)"
NS = {"a": "http://www.w3.org/2005/Atom"}
HERE = Path(__file__).resolve().parent
HTTP_LOG = []


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http(url, headers=None, data=None, pace=2.0):
    """GET/POST honouring Reddit's x-ratelimit headers; retries 429 up to 4 times."""
    for _ in range(4):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                code, body, h = r.status, r.read(), r.headers
        except urllib.error.HTTPError as e:
            code, body, h = e.code, e.read(), e.headers
        except urllib.error.URLError as e:
            HTTP_LOG.append({"status": None, "url": url, "error": str(e.reason)})
            return None, b""
        HTTP_LOG.append({"status": code, "url": url})
        remaining = float(h.get("x-ratelimit-remaining") or 1)
        reset = float(h.get("x-ratelimit-reset") or pace)
        if code == 429:
            log(f"  429 rate-limited, waiting {reset + 2:.0f}s")
            time.sleep(reset + 2)
            continue
        log(f"  {code} {url[:110]}")
        if remaining < 1:
            log(f"  rate budget spent, waiting {reset + 2:.0f}s")
            time.sleep(reset + 2)
        else:
            time.sleep(pace)
        return code, body
    return code, b""


# ---------- credentials / OAuth ----------

def load_creds():
    keys = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")
    found = {k: os.environ.get(k) for k in keys}
    for f in (HERE / ".env", Path.home() / ".config/topic-scout/reddit.env"):
        if all(found.values()) or not f.exists():
            continue
        for line in f.read_text().splitlines():
            k, _, v = line.strip().partition("=")
            if k in keys and not found.get(k):
                found[k] = v.strip().strip("'\"")
    return found if all(found.values()) else None


def oauth_token(creds):
    auth = base64.b64encode(f"{creds['REDDIT_CLIENT_ID']}:{creds['REDDIT_CLIENT_SECRET']}".encode()).decode()
    code, body = http("https://www.reddit.com/api/v1/access_token",
                      headers={"Authorization": f"Basic {auth}"},
                      data=b"grant_type=client_credentials", pace=0.5)
    try:
        tok = json.loads(body).get("access_token") if code == 200 else None
    except ValueError:
        tok = None
    if not tok:
        log(f"  OAuth token call failed (HTTP {code}); falling back to RSS")
    return tok


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def oauth_search(tok, a):
    h = {"Authorization": f"bearer {tok}"}
    base = f"https://oauth.reddit.com/r/{'+'.join(a.subs)}/search" if a.subs else "https://oauth.reddit.com/search"
    q = {"q": a.query, "sort": a.sort, "t": a.t, "limit": a.limit, "raw_json": 1, "type": "link"}
    if a.subs:
        q["restrict_sr"] = 1
    code, body = http(f"{base}?{urllib.parse.urlencode(q)}", headers=h, pace=0.7)
    if code != 200:
        return None
    posts = []
    for c in json.loads(body)["data"]["children"]:
        d = c["data"]
        posts.append(dict(id=d["id"], title=d["title"], subreddit=d["subreddit"], author=d.get("author"),
                          created=iso(d.get("created_utc")), score=d.get("score"),
                          num_comments=d.get("num_comments"),
                          permalink="https://www.reddit.com" + d["permalink"],
                          url=d.get("url"), body=d.get("selftext") or "", comments=[]))
    return posts


def oauth_comments(tok, p, n):
    code, body = http(f"https://oauth.reddit.com/comments/{p['id']}?" +
                      urllib.parse.urlencode({"sort": "top", "limit": n + 5, "depth": 1, "raw_json": 1}),
                      headers={"Authorization": f"bearer {tok}"}, pace=0.7)
    if code != 200:
        return
    out = []
    for c in json.loads(body)[1]["data"]["children"]:
        d = c.get("data", {})
        if c.get("kind") != "t1" or skip_comment(d.get("author"), d.get("body")):
            continue
        out.append(dict(author=d.get("author"), score=d.get("score"), body=d.get("body", "")[:1500]))
    p["comments"] = out[:n]


# ---------- RSS ----------

def plain(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(h or "")))).strip()


def rss_entries(body):
    try:
        return ET.fromstring(body).findall("a:entry", NS)
    except ET.ParseError:
        return []


def rss_search(a):
    base = f"https://www.reddit.com/r/{'+'.join(a.subs)}/search.rss" if a.subs else "https://www.reddit.com/search.rss"
    q = {"q": a.query, "sort": a.sort, "t": a.t, "limit": a.limit}
    if a.subs:
        q["restrict_sr"] = 1
    code, body = http(f"{base}?{urllib.parse.urlencode(q, quote_via=urllib.parse.quote)}")
    posts = []
    for e in rss_entries(body):
        eid = e.findtext("a:id", "", NS)
        if not eid.startswith("t3_"):  # search feed mixes in subreddit hits
            continue
        cat = e.find("a:category", NS)
        title = e.findtext("a:title", "", NS)
        body_txt = plain(e.findtext("a:content", "", NS))
        posts.append(dict(id=eid[3:], title=title, subreddit=(cat.get("term") if cat is not None else None),
                          author=e.findtext("a:author/a:name", "", NS).replace("/u/", "") or None,
                          created=e.findtext("a:published", "", NS) or e.findtext("a:updated", "", NS),
                          score=None, num_comments=None,
                          permalink=e.find("a:link", NS).get("href"), url=None,
                          body=body_txt.replace(title, "", 1).strip(), comments=[]))
    return posts if code == 200 else (posts or None)


def rss_comments(p, n):
    code, body = http(p["permalink"].rstrip("/") + "/.rss?sort=top&limit=100&depth=1")
    es = rss_entries(body)[1:]  # first entry is the post itself
    if code != 200 and not es:
        return
    p["num_comments"] = len(es)  # lower bound, capped at 100
    out = []
    for c in es:
        author = c.findtext("a:author/a:name", "", NS).replace("/u/", "")
        text = plain(c.findtext("a:content", "", NS))
        if not skip_comment(author, text):
            out.append(dict(author=author, score=None, body=text[:1500]))
    p["comments"] = out[:n]


def skip_comment(author, body):
    return not author or author in ("AutoModerator", "[deleted]") or (body or "").strip() in ("[deleted]", "[removed]", "")


# ---------- filtering ----------

def exact_match(query, text):
    """True if text has every word of at least one OR-alternative of the query."""
    text = text.lower()
    for alt in re.split(r"\s+OR\s+", query):
        words = [w for w in re.findall(r"[\w']+", alt.lower()) if w not in ("and", "not")]
        if words and all(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--subs", default="", help="comma-separated subreddits (restrict search to these)")
    ap.add_argument("--t", default="month", choices=["hour", "day", "week", "month", "year", "all"])
    ap.add_argument("--sort", default="relevance", choices=["relevance", "hot", "top", "new", "comments"])
    ap.add_argument("--limit", type=int, default=15, help="search results to request (max 100)")
    ap.add_argument("--comments", type=int, default=8, help="top comments to keep per opened thread")
    ap.add_argument("--threads", type=int, default=12, help="max threads to open for comments")
    ap.add_argument("--exact", action="store_true", help="drop posts whose title+body lack any query word")
    ap.add_argument("--rss", action="store_true", help="force RSS even if API credentials exist")
    a = ap.parse_args()
    a.subs = [re.sub(r"^/?r/", "", s.strip()) for s in a.subs.split(",") if s.strip()]
    a.limit = max(1, min(a.limit, 100))

    source, tok, posts = "rss", None, None
    creds = None if a.rss else load_creds()
    if creds:
        log("credentials found; using official API")
        tok = oauth_token(creds)
    if tok:
        posts = oauth_search(tok, a)
        if posts is None:
            log("  API search failed; falling back to RSS")
        else:
            source = "api"
    if posts is None:
        log("using public RSS (no scores; ~1 req/min)")
        posts = rss_search(a)
    if posts is None:
        print(json.dumps({"query": a.query, "source": source, "error": "search failed",
                          "http_log": HTTP_LOG}, indent=2))
        sys.exit(1)

    found = len(posts)
    if a.exact:
        posts = [p for p in posts if exact_match(a.query, p["title"] + " " + p["body"])]
        log(f"--exact kept {len(posts)}/{found} posts")

    # API: rank by real comment count. RSS: counts are unknown until opened, so open in search order.
    if source == "api":
        posts.sort(key=lambda p: -(p["num_comments"] or 0))
    to_open = posts[:max(0, a.threads)]
    log(f"opening {len(to_open)} thread(s) for comments")
    for p in to_open:
        oauth_comments(tok, p, a.comments) if source == "api" else rss_comments(p, a.comments)
    if source == "rss":
        posts.sort(key=lambda p: -(p["num_comments"] if p["num_comments"] is not None else -1))

    for p in posts:
        p["body"] = p["body"][:2000]
    print(json.dumps({
        "query": a.query, "source": source, "subs": a.subs, "t": a.t, "sort": a.sort,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "posts_found": found, "posts_returned": len(posts), "threads_opened": len(to_open),
        "notes": None if source == "api" else
            "RSS: score is null; num_comments is a lower bound (max 100) and null for unopened threads; "
            "threads were opened in search-relevance order, not by comment count.",
        "posts": posts, "http_log": HTTP_LOG,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
