"""Topic Scout app server: a JSON API for briefs plus the installable web app in ./static."""
import hmac
import json
import os
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
# Load .env (same file reddit_scout.py reads for REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET)
if (HERE / ".env").exists():
    for line in (HERE / ".env").read_text().splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and not k.startswith("#"):
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
DATA = Path(os.environ.get("TOPIC_SCOUT_DATA", HERE / "data")) / "briefs"
DATA.mkdir(parents=True, exist_ok=True)
APP_TOKEN = os.environ.get("APP_TOKEN", "")
if len(APP_TOKEN) < 12:
    raise SystemExit("Set APP_TOKEN (at least 12 characters) in .env before starting the server.")

import pipeline  # noqa: E402  (imported after the env check so a missing key fails fast above)

app = FastAPI(title="Topic Scout", docs_url=None, redoc_url=None)
lock = threading.Lock()
# Reddit RSS is rate-limited per IP, so run one brief at a time and queue the rest.
runner = threading.Semaphore(1)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path(bid):
    if not all(c.isalnum() for c in bid):
        raise HTTPException(404)
    return DATA / f"{bid}.json"


def load(bid):
    p = path(bid)
    if not p.exists():
        raise HTTPException(404)
    return json.loads(p.read_text())


def save(job):
    with lock:
        tmp = path(job["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1))
        tmp.replace(path(job["id"]))


def auth(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token.encode(), APP_TOKEN.encode()):
        raise HTTPException(401, "Wrong or missing app token")


class NewBrief(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    depth: Literal["quick", "standard", "deep"] = "standard"
    window: Literal["7d", "30d", "1y"] = "30d"
    reddit: bool = True
    notes: str = Field(default="", max_length=1000)


def work(job):
    def log(msg):
        job["progress"].append({"t": now(), "msg": msg})
        save(job)

    with runner:
        job["status"] = "running"
        log("Started")
        try:
            brief, meta = pipeline.run(job, log)
            job.update(status="done", brief=brief, meta=meta, finished=now())
            log("Done")
        except Exception as e:  # noqa: BLE001 - surface any failure to the phone
            traceback.print_exc()
            job.update(status="failed", error=f"{type(e).__name__}: {e}", finished=now())
            log("Failed")


@app.post("/api/briefs", dependencies=[Depends(auth)])
def create(req: NewBrief):
    job = dict(id=uuid.uuid4().hex[:12], created=now(), status="queued", progress=[],
               brief=None, meta=None, error=None, **req.model_dump())
    save(job)
    threading.Thread(target=work, args=(job,), daemon=True).start()
    return {"id": job["id"]}


@app.get("/api/briefs", dependencies=[Depends(auth)])
def list_briefs():
    out = []
    for p in DATA.glob("*.json"):
        j = json.loads(p.read_text())
        out.append({k: j.get(k) for k in ("id", "topic", "depth", "window", "status", "created", "finished")})
    return sorted(out, key=lambda j: j["created"], reverse=True)


@app.get("/api/briefs/{bid}", dependencies=[Depends(auth)])
def get_brief(bid: str):
    return load(bid)


@app.delete("/api/briefs/{bid}", dependencies=[Depends(auth)])
def delete_brief(bid: str):
    load(bid)
    path(bid).unlink()
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True, "model": pipeline.MODEL}


@app.on_event("startup")
def recover():
    # A restart kills in-flight threads; mark those briefs failed instead of leaving them spinning.
    for p in DATA.glob("*.json"):
        j = json.loads(p.read_text())
        if j["status"] in ("queued", "running"):
            j.update(status="failed", error="Server restarted while this brief was running. Run it again.")
            p.write_text(json.dumps(j, ensure_ascii=False, indent=1))


@app.get("/")
def index():
    return FileResponse(HERE / "static/index.html", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=HERE / "static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8787")))
