"""the launcher: one window with tabs for what was caught, and a thread per person.

`heyphony open` exists because an agent has no eyes, and a cli mailbox is the right shape for a
process reading one message at a time. this is the complementary shape: the same inbox, drawn the
way a phone app draws it, for the human who wants to see at a glance what arrived and who it came
from. three tabs, because there are three kinds of thing a number catches - texts, voicemail and
calls - and one thread per person, because that is how a person reads their own phone.

what it deliberately does not do is send. replying composes a draft, resolves it against the thread
and shows the route it would take and what is missing for it. an outbound path that half works is
worse than a draft that says exactly what it needs: sending is the half of telephony with
consequences, and this is a viewer.

stdlib only: http.server, one html string, json endpoints. no build step, no node_modules, no
database. the state is the same jsonl inbox, sidecars and sqlite the cli already reads, so nothing
here can disagree with what an agent sees.
"""
import json
import pathlib
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from heyphony.src.manage import inbox
from heyphony.src.manage import mailparse
from heyphony.src import providers
from heyphony.src.setup import routes
from heyphony.src.linphone import sip
from heyphony.src.manage import views

TABS = ("messages", "voicemail", "calls")


def _rows(path=None):
    rows = []
    for entry in inbox.read(path=path) or []:
        rows.append(entry)
    return rows


def _claimed_audio(rows):
    """voicemail files an inbox entry already accounts for.

    a carrier email that arrives as a forwarded message keeps its recording in the voicemail folder,
    so the same voicemail exists twice: once as the message, once as the file. a person wants to see
    it once, in its thread, and this is the set that says which file is already spoken for.
    """
    claimed = set()
    for row in rows:
        audio = row.get("audio") or {}
        name = audio.get("name") or audio.get("path")
        if name:
            claimed.add(pathlib.Path(name).name)
            claimed.add(str(name))
    return claimed


def voicemails(voicemail_dir=None, path=None, limit=200):
    """voicemail rows with a human timestamp, because an epoch in a list is a bug a person sees.

    voicemail_dir is the folder; path is accepted so a caller holding one location can pass it in
    either position without quietly reading the default folder instead.
    """
    answer = views.voicemail(path=voicemail_dir or path, limit=limit)
    for row in answer.get("rows", []):
        row["when"] = _when(row.get("at"))
    return answer


_voice = voicemails


def threads(path=None, voicemail_dir=None, limit=50):
    """one thread per peer, with texts and voicemail merged: what a person sees, not what arrived."""
    rows = _rows(path)
    claimed = _claimed_audio(rows)
    items = [dict(row, kind=row.get("kind") or "sms") for row in rows]
    voice = _voice(path=path, voicemail_dir=voicemail_dir)
    for row in voice.get("rows", []):
        if pathlib.Path(str(row.get("id"))).name in claimed:
            continue
        items.append({"id": f"vm:{row['id']}", "channel": "voicemail", "kind": "voicemail",
                      "sender": row.get("from"), "body": row.get("transcript"),
                      "at": row.get("at"), "thread": row.get("from"),
                      "audio": row.get("file"), "verified": False})
    groups = {}
    for item in items:
        peer = str(item.get("sender") or item.get("thread") or "unknown")
        bucket = groups.setdefault(peer, {"peer": peer, "count": 0, "kinds": set(), "last": 0,
                                          "preview": "", "channels": set()})
        bucket["count"] += 1
        bucket["kinds"].add(item.get("kind"))
        bucket["channels"].add(item.get("channel"))
        stamp = float(item.get("at") or 0)
        if stamp >= bucket["last"]:
            bucket["last"] = stamp
            bucket["preview"] = (item.get("body") or item.get("subject") or "")[:88]
    out = []
    for bucket in groups.values():
        bucket["kinds"] = sorted(bucket["kinds"])
        bucket["channels"] = sorted(bucket["channels"])
        bucket["when"] = _when(bucket["last"])
        out.append(bucket)
    out.sort(key=lambda row: row["last"], reverse=True)
    return {"applied": False, "shape": "one thread per person", "count": len(out),
            "threads": out[:limit]}


def thread(peer, path=None, voicemail_dir=None):
    """everything said with one person, in order, whichever door it came through."""
    rows = _rows(path)
    claimed = _claimed_audio(rows)
    items = []
    for row in rows:
        if str(row.get("sender") or row.get("thread")) == str(peer):
            items.append({"id": row.get("id"), "kind": row.get("kind") or "sms",
                          "channel": row.get("channel"), "at": row.get("at"),
                          "body": row.get("body"), "subject": row.get("subject"),
                          "direction": row.get("direction") or "inbound"})
    for row in _voice(path=path, voicemail_dir=voicemail_dir).get("rows", []):
        if pathlib.Path(str(row.get("id"))).name in claimed:
            continue
        if str(row.get("from")) == str(peer):
            items.append({"id": f"vm:{row['id']}", "kind": "voicemail", "channel": "voicemail",
                          "at": row.get("at"), "body": row.get("transcript"),
                          "audio": row.get("file"), "direction": "inbound",
                          "seconds": row.get("seconds")})
    items.sort(key=lambda row: float(row.get("at") or 0))
    for row in items:
        row["when"] = _when(row.get("at"))
    return {"peer": peer, "count": len(items), "items": items,
            "reply": draft(peer, "", path=path)}


def calls(limit=40):
    answer = views.calls(limit=limit)
    rows = answer.get("rows", [])
    for row in rows:
        row["when"] = _when(row.get("at") or row.get("started"))
    return {"count": len(rows), "rows": rows, "missed": answer.get("missed", 0)}


def draft(peer, body, path=None):
    """compose a reply and resolve where it would go. it does not send, and says why not.

    the thread may have arrived as a text, as an email from the carrier, or as a voicemail that can
    only be called back. each of those has a different outbound path, and none of them is wired to
    spend money here, so the answer is a plan rather than a promise.
    """
    items = []
    for row in _rows(path):
        if str(row.get("sender") or row.get("thread")) == str(peer):
            items.append(row)
    items.sort(key=lambda row: float(row.get("at") or 0), reverse=True)
    last = items[0] if items else {}
    provider = (last.get("provider") or (last.get("raw") or {}).get("provider")
                or last.get("provider_hint"))
    channel = last.get("channel") or "sms"
    route = routes.ROUTES.get(provider or "", {})
    if not provider:
        outbound = {"now": False,
                    "why": "no provider on this thread's messages, so the route is unknown rather than assumed"}
    elif route.get("kind") in ("webhook-json", "url-forward", "post-to-url", "email"):
        outbound = {"now": False, "via": provider,
                    "why": "this thread arrived by provider event, and no outbound api path is wired: "
                           "compose here, send from the provider's own console or a configured smtp relay",
                    "would_use": route.get("send_hint") or "the provider's send endpoint"}
    elif route.get("kind") == "none":
        outbound = {"now": False, "via": provider,
                    "why": "this number cannot receive or send a text, so a reply is a phone call, not a message"}
    else:
        outbound = {"now": False, "via": provider,
                    "why": "the route exists but sending is not wired here on purpose"}
    return {"applied": False, "peer": peer, "body": body or None,
            "channel": channel, "provider": provider,
            "thread_has": len(items), "last_inbound": _when(last.get("at")) if last else None,
            "outbound": outbound,
            "note": "a draft, not a send. the text you write is what would go out once a send path is configured."}


def import_email(raw, save_dir=None, path=None):
    """a carrier email becomes a caught message. this is the door for forwarding, not for typing."""
    item = mailparse.parse(raw, save_dir=save_dir)
    sidecar = mailparse.sidecar_for(item) if item.get("audio") else None
    stored, reason = inbox.append(item, path=path)
    return {"applied": False, "stored": bool(stored), "reason": reason,
            "kind": item.get("kind"), "sender": item.get("sender"), "id": item.get("id"),
            "audio": (item.get("audio") or {}).get("name"), "sidecar": sidecar,
            "verified": False}


def _when(stamp):
    try:
        value = float(stamp)
    except (TypeError, ValueError):
        return None
    if not value:
        return None
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(value))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>heyphony</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 :root { color-scheme: light dark; --line: #d8d5cd; --muted: #6d6a63; --bg: #fbfaf7; --ink: #23211d; --accent: #1f6f4a; }
 @media (prefers-color-scheme: dark) { :root { --line: #33312d; --muted: #9a968d; --bg: #191815; --ink: #eceae4; --accent: #5fbf8c; } }
 * { box-sizing: border-box; }
 body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 ui-sans-serif, system-ui, sans-serif; }
 header { display: flex; align-items: baseline; gap: 16px; padding: 14px 18px; border-bottom: 1px solid var(--line); }
 header h1 { font-size: 15px; margin: 0; letter-spacing: .02em; }
 header .note { color: var(--muted); font-size: 12px; }
 nav { display: flex; gap: 4px; padding: 10px 18px 0; }
 nav button { background: none; border: 1px solid transparent; border-bottom: none; color: var(--muted);
              padding: 7px 12px; border-radius: 6px 6px 0 0; cursor: pointer; font: inherit; font-size: 13px; }
 nav button[aria-selected="true"] { color: var(--ink); border-color: var(--line); background: var(--bg); }
 main { display: grid; grid-template-columns: 300px 1fr; gap: 0; border-top: 1px solid var(--line); min-height: 70vh; }
 .list { border-right: 1px solid var(--line); overflow: auto; max-height: 76vh; }
 .list .row { padding: 10px 14px; border-bottom: 1px solid var(--line); cursor: pointer; }
 .list .row:hover, .list .row[aria-current="true"] { background: rgba(127,127,127,.08); }
 .list .peer { font-weight: 600; font-size: 13px; }
 .list .prev { color: var(--muted); font-size: 12px; }
 .pane { padding: 16px 20px; overflow: auto; max-height: 76vh; }
 .msg { margin: 0 0 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; max-width: 46em; }
 .msg .meta { color: var(--muted); font-size: 11px; margin-bottom: 4px; }
 .msg.voicemail { border-left: 3px solid var(--accent); }
 textarea { width: 100%; max-width: 46em; min-height: 84px; padding: 10px; border: 1px solid var(--line);
            border-radius: 10px; background: transparent; color: inherit; font: inherit; }
 .actions { display: flex; gap: 10px; align-items: center; margin-top: 8px; }
 button.primary { background: var(--accent); color: #fff; border: none; border-radius: 8px; padding: 8px 14px; cursor: pointer; font: inherit; }
 .plan { color: var(--muted); font-size: 12px; max-width: 46em; }
 .empty { color: var(--muted); font-size: 13px; padding: 20px; }
</style></head>
<body>
<header><h1>heyphony</h1><span class="note">what a number caught. a viewer, not a sender.</span></header>
<nav role="tablist">
  <button role="tab" data-tab="messages" aria-selected="true">caught messages</button>
  <button role="tab" data-tab="voicemail" aria-selected="false">voicemail</button>
  <button role="tab" data-tab="calls" aria-selected="false">calls</button>
</nav>
<main>
  <div class="list" id="list"></div>
  <div class="pane" id="pane"><p class="empty">pick a thread on the left.</p></div>
</main>
<script>
const list = document.getElementById('list'), pane = document.getElementById('pane');
let tab = 'messages', peer = null;
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
async function get(path) { const r = await fetch(path); return r.json(); }
function select(name) { peer = name; document.querySelectorAll('.row').forEach(r => r.setAttribute('aria-current', r.dataset.peer === name ? 'true' : 'false')); showThread(name); }
async function loadList() {
  list.innerHTML = '';
  if (tab === 'calls') {
    const data = await get('/api/calls');
    if (!data.rows.length) { list.append(el('p', 'empty', 'no calls in the log yet.')); return; }
    for (const row of data.rows) {
      const rowEl = el('div', 'row'); rowEl.dataset.peer = row.who || '';
      rowEl.append(el('div', 'peer', (row.who || 'unknown') + (row.missed ? '  missed' : '')));
      rowEl.append(el('div', 'prev', (row.when || '') + '  ' + (row.direction || '')));
      rowEl.onclick = () => select(row.who || '');
      list.append(rowEl);
    }
    return;
  }
  const data = await get(tab === 'voicemail' ? '/api/voicemail' : '/api/threads');
  const rows = data.threads || data.rows || [];
  if (!rows.length) { list.append(el('p', 'empty', 'nothing caught yet. text the number, or forward a carrier email in.')); return; }
  for (const row of rows) {
    const rowEl = el('div', 'row');
    const who = row.peer || row.from || 'unknown';
    rowEl.dataset.peer = who;
    rowEl.append(el('div', 'peer', who + (row.kinds && row.kinds.includes('voicemail') ? '  vm' : '')));
    rowEl.append(el('div', 'prev', (row.when || row.at || '') + '  ' + (row.preview || row.transcript || '')));
    rowEl.onclick = () => select(who);
    list.append(rowEl);
  }
}
async function showThread(name) {
  pane.innerHTML = '';
  if (!name) { pane.append(el('p', 'empty', 'pick a thread on the left.')); return; }
  const data = await get('/api/thread?peer=' + encodeURIComponent(name));
  if (!data.items || !data.items.length) { pane.append(el('p', 'empty', 'nothing on this thread yet.')); return; }
  for (const item of data.items) {
    const box = el('div', 'msg' + (item.kind === 'voicemail' ? ' voicemail' : ''));
    box.append(el('div', 'meta', [item.kind, item.when || '', item.seconds ? item.seconds + 's' : ''].filter(Boolean).join('  ')));
    box.append(el('div', null, item.body || '(no transcript for this one)'));
    if (item.audio) { const a = el('audio', null); a.controls = true; a.src = '/audio?file=' + encodeURIComponent(item.audio); a.style.width = '100%'; a.style.marginTop = '8px'; box.append(a); }
    pane.append(box);
  }
  const area = el('textarea'); area.placeholder = 'reply to ' + name;
  const actions = el('div', 'actions');
  const send = el('button', 'primary', 'draft reply');
  const plan = el('div', 'plan');
  send.onclick = async () => {
    const r = await fetch('/api/reply', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ peer: name, body: area.value }) });
    const answer = await r.json();
    plan.textContent = 'draft kept, not sent. ' + (answer.outbound ? (answer.outbound.why || '') : '');
  };
  actions.append(send, plan);
  pane.append(area, actions);
}
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  tab = b.dataset.tab;
  document.querySelectorAll('nav button').forEach(x => x.setAttribute('aria-selected', x === b ? 'true' : 'false'));
  pane.innerHTML = ''; pane.append(el('p', 'empty', 'pick a thread on the left.'));
  loadList();
});
loadList();
</script></body></html>"""


def make_handler(home=None, path=None, voicemail_dir=None, audio_dir=None):
    """the http surface. kept small on purpose: six routes, no templating, no auth beyond a bind address."""

    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload, code=200):
            body = json.dumps(payload, indent=2).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, text):
            body = text.encode()
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path in ("/", "/index.html"):
                return self._html(PAGE)
            if parsed.path == "/api/threads":
                return self._json(threads(path=path, voicemail_dir=voicemail_dir))
            if parsed.path == "/api/thread":
                return self._json(thread((query.get("peer") or [""])[0], path=path, voicemail_dir=voicemail_dir))
            if parsed.path == "/api/voicemail":
                return self._json(_voice(path=path, voicemail_dir=voicemail_dir, limit=100))
            if parsed.path == "/api/calls":
                return self._json(calls())
            if parsed.path == "/api/tabs":
                return self._json({"tabs": list(TABS), "reply": "drafts only"})
            if parsed.path == "/audio":
                return self._audio((query.get("file") or [""])[0])
            return self._json({"ok": False, "why": "no such route"}, 404)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                payload = {}
            if parsed.path == "/api/reply":
                return self._json(draft(payload.get("peer", ""), payload.get("body", ""), path=path))
            if parsed.path == "/api/import":
                return self._json(import_email(payload.get("raw") or payload.get("email") or "",
                                               save_dir=voicemail_dir or views.voicemail_dir(home),
                                               path=path))
            return self._json({"ok": False, "why": "no such route"}, 404)

        def _audio(self, name):
            folder = pathlib.Path(audio_dir or views.voicemail_dir(home))
            target = (folder / pathlib.Path(name).name)
            if not target.is_file():
                return self._json({"ok": False, "why": "no such voicemail file"}, 404)
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("content-type", "audio/wav" if target.suffix == ".wav" else "audio/mpeg")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # a viewer should not spam a terminal
            return

    return Handler


def serve(port=8790, host="127.0.0.1", home=None, path=None, voicemail_dir=None):
    handler = make_handler(home=home, path=path, voicemail_dir=voicemail_dir)
    server = ThreadingHTTPServer((host, port), handler)
    return server


def providers_seen(path=None):
    """which hooks are live, so the page can say why a reply is a draft rather than a send."""
    seen = {}
    for row in _rows(path):
        name = row.get("provider") or (row.get("raw") or {}).get("provider")
        if name:
            seen[name] = seen.get(name, 0) + 1
    return {"providers": seen, "known": [p for p in seen if p in providers.PROVIDERS],
            "reply": "drafts only: no outbound api path is wired for any provider"}
