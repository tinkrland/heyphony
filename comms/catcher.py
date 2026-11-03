"""the catcher for the umbrella's lanes: email, imessage, whatsapp, slack, telegram.

each route verifies its own scheme before anything is parsed or stored, and every
stored message lands in the shared inbox with channel set. sms is not here: texts
belong to the telephony folder, which catches its own provider events.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from comms import envelope, gates
from comms.recognica import cards as cardbook
from comms import number

ROUTES = {"email": "email", "mail": "email", "imessage": "imessage",
          "whatsapp": "whatsapp", "slack": "slack", "telegram": "telegram"}


def pick(payload, *keys):
    """walk down a few layers: vendors nest their own payloads differently every release."""
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


def normalize(channel, payload):
    if channel == "email":
        sender = pick(payload, "from", "sender")
        body = pick(payload, "text", "html", "body")
        subject = pick(payload, "subject", "title")
    elif channel == "imessage":
        message = payload.get("message", {}) or {}
        sender = (message.get("sender") or {}).get("id")
        body = message.get("text") or pick(payload, "body", "text")
        subject = None
    elif channel == "whatsapp":
        sender = pick(payload, "from", "chatId", "author")
        body = pick(payload, "body", "text")
        subject = None
    else:
        event = payload.get("event", {}) or {}
        sender, body, subject = event.get("user"), event.get("text"), None
    entry = envelope.envelope(channel, id=pick(payload, "message_id", "id", "guid"),
                              sender=sender, recipient=pick(payload, "to", "chatId"),
                              subject=subject, body=body, at=pick(payload, "date", "timestamp", "at"),
                              raw=payload)
    if not entry["at"]:
        entry["at"] = int(time.time())
    return entry


def verify(channel, raw, headers, env=None):
    if channel == "email":
        from comms import registry
        return registry._load("email").verify(headers, raw, env)
    if channel == "imessage":
        from comms import gates as g
        import os
        return g.v0(raw, headers, (env or os.environ).get("PHOTON_SIGNING_SECRET", ""))
    if channel == "whatsapp":
        import os
        return gates.waha(raw, headers, (env or os.environ).get("WAHA_HMAC_KEY", ""))
    import os
    return gates.slack(raw, headers, (env or os.environ).get("SLACK_SIGNING_SECRET", ""))


def make_handler(path=None, env=None):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_POST(self):
            route = self.path.rstrip("/").lstrip("/") or "email"
            channel = ROUTES.get(route)
            if not channel:
                self._reply(404, {"error": f"no such lane: {route}"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = (self.rfile.read(length) if length else b"{}").decode("utf-8", "replace")
            headers = {k.lower(): v for k, v in self.headers.items()}
            if channel == "telegram":
                # telegram's lane owns its own header gate, whitelist and group refusal
                from comms import registry
                answer = registry._load("telegram").handle(raw, headers, env)
                if answer["status"] == 200:
                    entry = answer["body"]["envelope"]
                    known = cardbook.resolve(cardbook.load(env), entry["channel"], entry["sender"])
                    if known.get("card"):
                        entry["card"] = known["card"]
                    stored, reason = number.inbox().append(entry, path)
                    self._reply(200, {"stored": stored, "reason": reason, "lane": channel})
                    return
                self._reply(answer["status"], answer["body"])
                return
            ok, why = verify(channel, raw, headers, env)
            if not ok:
                self._reply(401, {"rejected": why})
                return
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {"unparsed": raw}
            entry = normalize(channel, payload)
            known = cardbook.resolve(cardbook.load(env), entry["channel"], entry["sender"] or "")
            if known.get("card"):
                entry["card"] = known["card"]
            stored, reason = number.inbox().append(entry, path)
            self._reply(200 if stored or reason == "duplicate" else 500,
                        {"stored": stored, "reason": reason, "lane": channel})

        def do_GET(self):
            from comms import registry
            self._reply(200, {"lanes": registry.states(env)})

        def log_message(self, *a):
            pass

    return Handler


def serve(port=8098, path=None, env=None):
    httpd = HTTPServer(("0.0.0.0", port), make_handler(path, env))
    httpd.serve_forever()
