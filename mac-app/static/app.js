"use strict";
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view");
const PRICE = { "claude-opus-5-5": [4, 20], "claude-sonnet-5-5": [2, 10], "claude-fable-5-1": [10, 50] };
const EST = { quick: "about $0.30 and 3 to 5 min", standard: "about $1 to $1.50 and 5 to 8 min", deep: "about $3 to $4 and 10 to 15 min" };
let pollTimer = null;

function store(k, v) {
  try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); }
  catch { return null; }
}
const token = () => store("ts_token") || "";

async function api(path, opts = {}) {
  const r = await fetch("api/" + path, {
    ...opts, headers: { "Content-Type": "application/json", Authorization: "Bearer " + token(), ...(opts.headers || {}) },
  });
  if (r.status === 401) {
    store("ts_token", null);
    if (location.hash !== "#/setup") location.hash = "#/setup";
    throw new Error("That token was rejected. Check APP_TOKEN in the server's .env.");
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

function toast(msg) {
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 2200);
}
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ago = iso => {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "just now"; if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " h ago"; return new Date(iso).toLocaleDateString();
};

// Minimal, safe markdown: everything is escaped first, then a small subset is re-enabled.
function inline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`);
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, (_, p, u) => `${p}<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  return s;
}
function md(src) {
  const out = []; let list = null; let para = [];
  const flushP = () => { if (para.length) { out.push("<p>" + inline(para.join(" ")) + "</p>"); para = []; } };
  const flushL = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of src.split("\n")) {
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { flushP(); flushL(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flushP(); flushL(); const n = m[1].length; out.push(`<h${n}>${inline(m[2])}</h${n}>`); continue; }
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) { flushP(); flushL(); out.push("<hr>"); continue; }
    if ((m = line.match(/^\s*[-*•]\s+(.*)/)) || (m = line.match(/^\s*\d+[.)]\s+(.*)/))) {
      flushP(); const kind = /^\s*\d/.test(line) ? "ol" : "ul";
      if (list !== kind) { flushL(); out.push(`<${kind}>`); list = kind; }
      out.push("<li>" + inline(m[1]) + "</li>"); continue;
    }
    flushL(); para.push(line.trim());
  }
  flushP(); flushL();
  return out.join("\n");
}

function render(tplId) { view.replaceChildren($("#" + tplId).content.cloneNode(true)); }

function setup() {
  render("tpl-setup");
  if (location.hash !== "#/setup") history.replaceState(null, "", "#/setup");
  $("#setupForm").onsubmit = async e => {
    e.preventDefault();
    store("ts_token", $("#token").value.trim());
    try { await api("briefs"); location.hash = "#/"; }
    catch (err) { $("#setupErr").textContent = err.message; }
  };
}

async function home() {
  render("tpl-home");
  const choice = { depth: store("ts_depth") || "standard", window: "30d" };
  document.querySelectorAll(".seg").forEach(seg => {
    const name = seg.dataset.name;
    seg.querySelectorAll("button").forEach(b => {
      b.classList.toggle("on", b.dataset.v === choice[name]);
      b.onclick = () => {
        choice[name] = b.dataset.v;
        seg.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
        if (name === "depth") { store("ts_depth", b.dataset.v); est(); }
      };
    });
  });
  const est = () => { $("#estimate").textContent = `Estimated ${EST[choice.depth]}, or longer with Reddit on.`; };
  est();
  $("#reddit").checked = store("ts_reddit") !== "0";
  $("#reddit").onchange = e => store("ts_reddit", e.target.checked ? "1" : "0");
  $("#newForm").onsubmit = async e => {
    e.preventDefault();
    $("#runBtn").disabled = true;
    try {
      const { id } = await api("briefs", { method: "POST", body: JSON.stringify({
        topic: $("#topic").value.trim(), depth: choice.depth, window: choice.window,
        reddit: $("#reddit").checked, notes: $("#notes").value.trim() }) });
      location.hash = "#/b/" + id;
    } catch (err) { toast(err.message); $("#runBtn").disabled = false; }
  };
  try {
    const items = await api("briefs");
    $("#history").innerHTML = items.length ? items.map(b => `
      <li><a href="#/b/${esc(b.id)}"><div class="t">${esc(b.topic)}</div>
      <div class="m"><span class="pill ${esc(b.status)}">${esc(b.status)}</span>${esc(b.depth)} · ${esc(b.window)} · ${ago(b.created)}</div></a></li>`).join("")
      : `<li class="muted small">No briefs yet. Your first one will show up here.</li>`;
    if (items.some(b => b.status === "running" || b.status === "queued")) pollTimer = setTimeout(home, 8000);
  } catch (err) { $("#history").innerHTML = `<li class="err">${esc(err.message)}</li>`; }
}

function cost(meta) {
  const p = PRICE[meta.model]; if (!p) return "";
  const usd = meta.input_tokens / 1e6 * p[0] + meta.output_tokens / 1e6 * p[1] + (meta.web_searches || 0) * 0.01;
  return ` · ~$${usd.toFixed(2)}`;
}

async function brief(id) {
  render("tpl-brief");
  let b;
  try { b = await api("briefs/" + id); } catch (err) { $("#briefBody").innerHTML = `<p class="err">${esc(err.message)}</p>`; return; }
  const body = $("#briefBody");
  if (b.status === "done") {
    const m = b.meta || {};
    body.innerHTML = `<article class="card md">${md(b.brief)}</article>
      <p class="meta">${esc(m.model)} · ${Math.round((m.seconds || 0) / 60)} min · ${m.web_searches ?? 0} web searches ·
      ${m.reddit_posts ?? 0} Reddit posts · ${m.hn_stories ?? 0} HN stories${cost(m)}</p>`;
  } else {
    const live = b.status === "running" || b.status === "queued";
    body.innerHTML = `<section class="card"><h1>${esc(b.topic)}</h1>
      <p>${live ? '<span class="spinner"></span>' : ""}<span class="pill ${esc(b.status)}">${esc(b.status)}</span>
      ${live ? '<span class="muted small">You can close the app. The brief keeps running and lands in History.</span>' : ""}</p>
      ${b.error ? `<p class="err">${esc(b.error)}</p>` : ""}
      <ul class="progress">${b.progress.slice().reverse().map(p =>
        `<li><time>${new Date(p.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>${esc(p.msg)}</li>`).join("")}</ul></section>`;
    if (live) pollTimer = setTimeout(() => brief(id), 4000);
  }
  $("#copyBtn").onclick = async () => { await navigator.clipboard.writeText(b.brief || ""); toast("Copied as markdown"); };
  $("#shareBtn").onclick = async () => {
    const text = b.brief || b.topic;
    if (navigator.share) { try { await navigator.share({ title: b.topic, text }); } catch {} }
    else { await navigator.clipboard.writeText(text); toast("Copied"); }
  };
  $("#delBtn").onclick = async () => {
    if (!confirm("Delete this brief?")) return;
    await api("briefs/" + id, { method: "DELETE" }); location.hash = "#/";
  };
}

function route() {
  clearTimeout(pollTimer);
  const h = location.hash || "#/";
  if (!token() || h === "#/setup") return setup();
  const m = h.match(/^#\/b\/(\w+)/);
  return m ? brief(m[1]) : home();
}
$("#settingsBtn").onclick = () => { location.hash = "#/setup"; };
addEventListener("hashchange", route);
document.addEventListener("visibilitychange", () => { if (!document.hidden) route(); });
route();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
