"""the telephony catcher: sms provider callbacks become envelopes.

texts never arrive over sip, so a number's inbox is a webhook. an unknown payload
shape is still stored with its raw body, because losing a message because a vendor
renamed a field is the worse failure.
"""
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.manage import allow, inbox
from src.setup import routes


def pick(payload, *keys):
    def walk(layer, depth=0):
        if not isinstance(layer, dict) or depth > 3:
            return None
        for k in keys:
            if layer.get(k):
                return layer[k]
        for value in layer.values():
            if isinstance(value, dict):
                found = walk(value, depth + 1)
                if found:
                    return found
        return None
    return walk(payload)


def provider_of(path):
    """the provider named in /sms/<provider>, when it is one we have a route for."""
    parts = [p for p in urllib.parse.urlparse(path).path.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[0] == "sms" and parts[1] in routes.ROUTES:
        return parts[1]
    return None


def normalize(payload, provider=None):
    if provider:
        return routes.normalize(provider, payload)
    entry = {"id": pick(payload, "id", "message_id", "guid"), "channel": "sms",
             "direction": "inbound", "sender": pick(payload, "from", "source", "origination_number", "msisdn"),
             "recipient": pick(payload, "to", "destination", "destination_number"),
             "subject": None, "body": pick(payload, "body", "text", "message", "content"),
             "at": pick(payload, "at", "timestamp", "received_at") or int(time.time()),
             "thread": None, "media": routes.media_of(payload), "reply_to": None, "raw": payload}
    return entry


def make_handler(token=None, path=None, policy=None, refused=None, on_store=None):
    class Handler(BaseHTTPRequestHandler):
        def _store(self, payload, provider):
            entry = normalize(payload, provider)
            # reloaded per message: an edit to the policy takes effect on the next text, not the next restart
            allowed, why = allow.decide(entry.get("sender"), policy or allow.load())
            if not allowed:
                allow.record_refusal(entry.get("sender"), why, refused)
                # a refused sender is still news: somebody tried to reach this number, and the
                # rail that is watching (a call in progress, say) wants to know without polling
                if on_store:
                    on_store(entry, False, f"refused: {why}")
                # 200, not 403: a carrier that sees an error retries, and a retry storm of refused
                # messages is worse than the refusal. the body says what happened.
                body = json.dumps({"stored": False, "reason": "refused", "why": why}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
                return
            stored, reason = inbox.append(entry, path)
            if on_store:
                on_store(entry, stored, reason)
            body = json.dumps({"stored": stored, "reason": reason}).encode()
            self.send_response(200 if stored or reason == "duplicate" else 500)
            self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

        def _closed(self):
            if token and self.headers.get("X-Heyphony-Token") != token:
                self.send_response(401); self.end_headers(); self.wfile.write(b"no")
                return True
            return False

        def do_POST(self):
            if self._closed():
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            provider = provider_of(self.path)
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                form = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
                payload = {k: v[0] for k, v in form.items()} if form else {"unparsed": raw.decode("utf-8", "replace")}
            if not isinstance(payload, dict):
                payload = {"unparsed": payload}
            self._store(payload, provider)

        def do_GET(self):
            """anveo calls a url with the message spliced into the query string, so a get is a delivery."""
            if self._closed():
                return
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if not query:
                self.send_response(404); self.end_headers(); self.wfile.write(b"nothing here"); return
            self._store({k: v[0] for k, v in query.items()}, provider_of(self.path))

        def log_message(self, *a):
            pass

    return Handler


def serve(port=8099, token=None, path=None, policy=None, refused=None, on_store=None):
    ThreadingHTTPServer(("0.0.0.0", port),
                        make_handler(token, path, policy, refused, on_store)).serve_forever()
