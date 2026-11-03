"""whatsapp: a waha session, gated and digits-whitelisted.

ported from tinkrland/prixie.ai routes/webhooks/waha.ts. the session webhook signs
with hmac and says which algorithm in its own header; nothing about that should be
guessed from the body.
"""
import os
import re

from comms import gates

LANE = {
    "name": "whatsapp", "folder": "whatsapp",
    "carrier": "waha session webhook",
    "intake": "hmac webhook -> one envelope",
    "relay": "the same session the human uses",
    "gate": ("WAHA_HMAC_KEY",),
    "state": "designed",
    "evidence": "gate and whitelist ported; nobody has messaged this session yet",
}

# the number problem, as data so a card or a plan cannot improvise a different answer.
# the question is not "is it cloud" but "does this country treat a cloud number as a mobile
# number". those that do issue mobile ranges to cloud providers and expect carrier behaviour.
# the us, canada and the +1 countries put did, cloud and softphone in one bucket, which is
# refused. nothing here spoofs anything: the classification is the country's, not a disguise.
NUMBER_TYPES = {
    "googlevoice-like": {"region": "+1", "kind": "voip", "state": "refused"},
    "did": {"region": "+1", "kind": "voip", "state": "refused"},
    "esim-data": {"region": "any", "kind": "data", "state": "not-a-number"},
    "vmn-uk": {"region": "+44", "kind": "virtual mobile number", "state": "works",
               "cost": "more than a us number"},
    "vmn-australia": {"region": "+61", "kind": "virtual mobile number", "state": "works",
                      "cost": "more again than the uk"},
    "vmn-sweden": {"region": "+46", "kind": "virtual mobile number", "state": "works"},
    "vmn-lithuania": {"region": "+370", "kind": "virtual mobile number", "state": "works"},
    "vmn-poland": {"region": "+48", "kind": "virtual mobile number", "state": "works"},
    "vmn-netherlands": {"region": "+31", "kind": "virtual mobile number", "state": "works",
                        "cost": "expensive, and worth it only if the workflow already pays for itself"},
}

# two different jobs, and they are different numbers. fanytel is a web app, so no sip and no
# softphone: it signs an account up once and that is the whole of its use. a provider did in
# the same countries is real sip: it registers on the host, catches its texts and rings.
SIGNUP_NUMBER = {
    "provider": "fanytel",
    "hosted": "web app, not sip",
    "softphone": False,
    "works_for": "one signup, and the otp that comes with it",
    "cannot": "carry a softphone line, or answer when the agent's job is the call itself",
}

PROVIDER_DID = {
    "sip": True,
    "softphone": True,
    "works_for": "the line heyphony holds: registration, inbound texts, calls while the host is up",
    "providers": ["voip.ms", "anveo", "bulkvs", "jmp.chat"],
    "countries": ["+44", "+61", "+46", "+370", "+48", "+31"],
}

SURFACES = {
    "waha": {"what": "an automated session on the number", "state": "wired above"},
    "web.whatsapp.com": {"what": "the linked desktop in the guest's own browser",
                         "state": "supported surface, and the right one for reading"},
}


def number_plan():
    """which number type can carry this account, and what makes the answer different."""
    return {
        "works": "vmn",
        "regions": ["+44", "+61", "+46", "+370", "+48", "+31"],
        "cheapest_that_works": "+44 uk",
        "why": ("in these countries the numbering plan gives cloud providers mobile ranges and expects "
                "carrier behaviour, so the number is a mobile number by law rather than by disguise"),
        "refused": [k for k, v in NUMBER_TYPES.items() if v["state"] == "refused"],
        "signup_number": SIGNUP_NUMBER,
        "line_number": PROVIDER_DID,
        "cost": "uk costs more than us, australia more again, netherlands is the expensive one",
        "flow": ["one otp at setup, on the vmn, read in the provider's own web app",
                 "finish setup from the app on a warmed up mobile, then park the phone",
                 "connect web.whatsapp.com on the agent desktop by qr or login code",
                 "messages sync while the phone is offline, calls in and out work"],
        "still_not": "an esim, or a +1 number",
        "google": "a uk or australian number tends to work for google too, and it is the same cost question",
        "not_spoofing": ("no vpn, no borrowed identity, no faked location: the number is a mobile number "
                         "because the country issues it as one"),
        "verified": False,
        "evidence": "uk classification is the regulator's own category; nothing here has been signed up",
    }


def verify(raw_body, headers, env=None):
    env = env if env is not None else os.environ
    return gates.waha(raw_body, headers, env.get("WAHA_HMAC_KEY", ""))


def whitelisted(chat_id, env=None):
    """digits only, and a group id never passes: @g.us is refused before lookup."""
    env = env if env is not None else os.environ
    if "@g.us" in (chat_id or "") or "@broadcast" in (chat_id or ""):
        return False, "groups are never whitelisted: a room is not somebody asking"
    raw = env.get("HEYPHONY_WHATSAPP_WHITELIST")
    if not raw:
        return False, "whitelist unset, so no number is allowed"
    digits = lambda s: re.sub(r"\D", "", s or "")
    allowed = [digits(p) for p in raw.split(",")]
    return (True, "ok") if digits(chat_id) in allowed else (False, f"unlisted sender: {chat_id}")
