"""imessage: the photon webhook, gated the way prixie gated it.

ported from tinkrland/prixie.ai (routes/photon.ts, services/photon.ts): signature
checked against the RAW body before json parsing, five minute freshness, then the
sender whitelist. a message that fails the gate is never read.
"""
import os
import re

from comms import gates

E164 = re.compile(r"\+?\d{6,15}")

LANE = {
    "name": "imessage", "folder": "imessage",
    "carrier": "photon / spectrum webhook",
    "intake": "v0 signed webhook -> one envelope",
    "relay": "the provider's send endpoint, project creds gated",
    "gate": ("PHOTON_SIGNING_SECRET",),
    "scope": ("not a beast: photon free tier for whitelisted people, rcs fallback, and plain sms "
              "on the heyphony did underneath. no bridge of our own and no number ownership attempt"),
    "state": "designed",
    "evidence": "the v0 gate is ported and tested here; no real blue bubble has arrived",
}


def verify(raw_body, headers, env=None):
    env = env if env is not None else os.environ
    return gates.v0(raw_body, headers, env.get("PHOTON_SIGNING_SECRET", ""))


def whitelisted(sender, env=None):
    env = env if env is not None else os.environ
    raw = env.get("PHOTON_WHITELIST")
    if not raw:
        return False, "whitelist unset, so no number is allowed"
    digits = lambda s: re.sub(r"[^\d+]", "", s or "")
    allowed = [digits(p) for p in raw.split(",")]
    return (True, "ok") if digits(sender) in allowed else (False, f"unlisted sender: {sender}")


def relay_plan(to, body, env=None):
    env = env if env is not None else os.environ
    if not (env.get("PHOTON_PROJECT_ID") and env.get("PHOTON_PROJECT_SECRET")):
        return {"sendable": False, "why": "project creds unset, so the send lane is closed"}
    return {"sendable": True, "to": to, "body": body}
