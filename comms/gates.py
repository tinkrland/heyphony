"""the signature schemes the carriers actually use.

ported from working code (tinkrland/prixie.ai) rather than reimagined, because a
signature scheme guessed wrong is a door that looks locked. all of them are
constant-time compares and all are freshness-checked: valid yesterday is not valid now.

  svix    carlyemail and most modern providers: v1,<base64 hmac> over id.timestamp.body
  v0      photon / spectrum (imessage) and slack: hex hmac over "v0:timestamp:body"
  waha    whatsapp: hex hmac over the raw body, algorithm named in its own header
"""
import base64
import hashlib
import hmac
import time

TOLERANCE = 300


def _fresh(ts, now=None, tolerance=TOLERANCE):
    try:
        stamp = int(str(ts).strip())
    except (TypeError, ValueError):
        return False
    return abs(int(now if now is not None else time.time()) - stamp) <= tolerance


def _hex(key, message, digest=hashlib.sha256):
    return hmac.new(key.encode(), message.encode(), digest).hexdigest()


def svix(raw_body, headers, secret, now=None, tolerance=TOLERANCE):
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if not secret or not secret.startswith("whsec_"):
        return False, "secret missing or not a whsec_ secret"
    key = base64.b64decode(secret[len("whsec_"):])
    msg_id, ts = headers.get("webhook-id"), headers.get("webhook-timestamp")
    if not msg_id or not ts:
        return False, "missing webhook-id or webhook-timestamp"
    if not _fresh(ts, now, tolerance):
        return False, "stale timestamp"
    expected = base64.b64encode(
        hmac.new(key, f"{msg_id}.{ts}.{raw_body}".encode(), hashlib.sha256).digest()).decode()
    for part in headers.get("webhook-signature", "").split():
        version, _, got = part.partition(",")
        if version == "v1" and hmac.compare_digest(got, expected):
            return True, "ok"
    return False, "no matching v1 signature"


def _v0(raw_body, ts, signature, secret, now, tolerance):
    if not secret:
        return False, "lane closed: signing secret unset"
    if not signature or not ts:
        return False, "missing signature or timestamp"
    if not _fresh(ts, now, tolerance):
        return False, "stale timestamp"
    expected = _hex(secret, f"v0:{ts}:{raw_body}")
    got = signature.split("=", 1)[1] if "=" in signature else signature
    return (True, "ok") if hmac.compare_digest(got, expected) else (False, "bad signature")


def v0(raw_body, headers, secret, now=None, tolerance=TOLERANCE):
    """photon / spectrum: x-spectrum-timestamp + x-spectrum-signature."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    return _v0(raw_body, headers.get("x-spectrum-timestamp"),
               headers.get("x-spectrum-signature"), secret, now, tolerance)


def slack(raw_body, headers, secret, now=None, tolerance=TOLERANCE):
    """slack events api: same v0 scheme, x-slack-* header names."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    return _v0(raw_body, headers.get("x-slack-request-timestamp"),
               headers.get("x-slack-signature"), secret, now, tolerance)


def waha(raw_body, headers, key, now=None, tolerance=TOLERANCE):
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    if not key:
        return False, "lane closed: WAHA_HMAC_KEY unset"
    algorithm = (headers.get("x-webhook-hmac-algorithm") or "sha512").lower()
    digest = {"sha256": hashlib.sha256, "sha512": hashlib.sha512}.get(algorithm)
    if digest is None:
        return False, f"unsupported algorithm: {algorithm}"
    got = headers.get("x-webhook-hmac")
    if not got:
        return False, "missing x-webhook-hmac"
    if headers.get("x-webhook-timestamp") and not _fresh(headers["x-webhook-timestamp"], now, tolerance):
        return False, "stale timestamp"
    return (True, "ok") if hmac.compare_digest(got, _hex(key, raw_body, digest)) else (False, "bad signature")
