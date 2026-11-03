"""email: caught at the provider, whitelisted before it becomes work.

the rules are ported from tinkrland/prixie.ai's backend/src/routes/agentmail.ts and
routes/webhooks/carlyemail.ts, including the two people get backwards: an unset
secret closes the door, and a sender has to be listed before their mail is a task.
"""
import base64
import hashlib
import hmac
import os
import re

from comms import gates

ADDRESS = re.compile(r"[\w.+-]+@[\w.-]+")
SECRET_HEADER = "x-agentmail-secret"

LANE = {
    "name": "email", "folder": "email",
    "carrier": "agentmail / carlyemail inbound webhook, smtp outbound",
    "intake": "webhook -> one envelope in the shared jsonl inbox",
    "relay": "smtp only, gated by SMTP_URL",
    "gate": ("CARLYEMAIL_SIGNING_SECRET", "HEYPHONY_MAIL_SECRET"),
    "state": "designed",
    "evidence": "signature check, whitelist and normalisation ported from working code; this branch has not received real mail",
}

PROVIDERS = {
    "agentmail": {"free": "agentmail.to addresses only: a custom domain is a paid-plan feature",
                  "signature": "plain header secret", "verified": True,
                  "verified_what": "the domain paywall, per the owner; the plan's figures are still unread"},
    "carlyemail": {"free": "3 inboxes and 1000 emails a month, custom domain included, no card",
                   "signature": "svix (v1 over id.timestamp.body)", "verified": True,
                   "verified_what": "the free tier and the custom domain, from their own page"},
}


def verify(headers, raw_body="", env=None):
    env = env if env is not None else os.environ
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if "webhook-signature" in headers:
        secret = env.get("CARLYEMAIL_SIGNING_SECRET")
        if not secret:
            return False, "lane closed: CARLYEMAIL_SIGNING_SECRET is unset"
        return gates.svix(raw_body, headers, secret)
    expected = env.get("HEYPHONY_MAIL_SECRET")
    if not expected:
        return False, "lane closed: HEYPHONY_MAIL_SECRET is unset"
    return (True, "ok") if headers.get(SECRET_HEADER) == expected else (False, "bad secret")


def whitelisted(sender, env=None):
    env = env if env is not None else os.environ
    raw = env.get("HEYPHONY_FORWARD_WHITELIST")
    if not raw:
        return False, "whitelist unset, so no sender is allowed"
    found = ADDRESS.search(sender or "")
    if not found:
        return False, "sender has no address"
    allowed = [m.group(0).lower() for m in (ADDRESS.search(p) for p in raw.split(",")) if m]
    return (True, "ok") if found.group(0).lower() in allowed else (False, f"unlisted sender: {found.group(0)}")


def relay_plan(to, subject, body, env=None):
    env = env if env is not None else os.environ
    if not env.get("SMTP_URL"):
        return {"sendable": False, "why": "SMTP_URL unset, so the relay lane is closed"}
    return {"sendable": True, "to": to, "subject": subject, "body": body}
