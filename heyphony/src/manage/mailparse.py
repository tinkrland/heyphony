"""forwarded provider mail, turned back into a message with a person on it.

a carrier that emails a text or a voicemail recording is doing us a favour and also making a mess:
the useful facts are somewhere inside mime parts, the sender's number is sometimes in the subject,
sometimes in the body, and the audio is an attachment with a filename nobody chose. the two things
this module refuses to do are invent a sender it could not find, and keep the audio only in memory.

so: parse an rfc822 message into one caught item with a kind, a peer, a body and (for voicemail) a
file next to the inbox. the shapes here were written from published provider formats and are marked
unverified until one real specimen of each lands, which is exactly the kind of honesty that stops a
thread view from quietly attributing a stranger's message to whoever wrote last.
"""
import email
import email.policy
import hashlib
import json
import pathlib
import re
import time

PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".opus", ".au", ".gsm")
VOICE_WORDS = ("voicemail", "voice mail", "voice message", "new message from")
SMS_WORDS = ("sms", "text message", "new text")


def _text_of(message):
    """the first text/plain part, with html as the fallback nobody wants but everybody needs."""
    best = ""
    html = ""
    for part in message.walk():
        if part.get_content_maintype() != "text":
            continue
        if part.get_filename():
            continue
        try:
            payload = part.get_content()
        except (LookupError, KeyError):
            payload = part.get_payload(decode=True) or b""
            payload = payload.decode(part.get_content_charset() or "utf-8", "replace")
        if part.get_content_subtype() == "html":
            html = html or payload
        elif len(payload) > len(best):
            best = payload
    if best:
        return best
    stripped = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"[ \t]+", " ", stripped).strip()


def _attachments(message, save_dir=None):
    """audio attachments, written where the voicemail view reads. returns paths."""
    saved = []
    for part in message.walk():
        name = part.get_filename() or ""
        ctype = (part.get_content_type() or "").lower()
        if not (ctype.startswith("audio/") or pathlib.Path(name).suffix.lower() in AUDIO_EXT):
            continue
        payload = part.get_payload(decode=True) or b""
        if not payload:
            continue
        if save_dir is None:
            saved.append({"name": name, "bytes": len(payload), "saved": False})
            continue
        folder = pathlib.Path(save_dir)
        folder.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-z0-9]+", "-", pathlib.Path(name or "voicemail").stem.lower()).strip("-") or "voicemail"
        digest = hashlib.sha256(payload).hexdigest()[:8]
        suffix = pathlib.Path(name or "voicemail.wav").suffix.lower() or ".wav"
        target = folder / f"{int(time.time())}-{stem}-{digest}{suffix}"
        target.write_bytes(payload)
        saved.append({"name": target.name, "path": str(target), "bytes": len(payload), "saved": True})
    return saved


def _peer(*candidates):
    """the first number in what the carrier gave us. a number, or nothing: never a guess."""
    for candidate in candidates:
        if not candidate:
            continue
        found = PHONE.search(str(candidate))
        if found:
            digits = re.sub(r"[^\d+]", "", found.group(0))
            if digits.startswith("00"):
                digits = "+" + digits[2:]
            return digits if digits.startswith("+") else "+" + digits
    return None


def parse(raw, save_dir=None, now=None):
    """one caught item out of one forwarded email. kind is 'voicemail', 'sms' or 'email'."""
    if isinstance(raw, bytes):
        message = email.message_from_bytes(raw, policy=email.policy.default)
    else:
        message = email.message_from_string(str(raw), policy=email.policy.default)
    subject = str(message.get("Subject") or "")
    from_header = str(message.get("From") or "")
    at = message.get("Date")
    try:
        stamp = email.utils.parsedate_to_datetime(at).timestamp() if at else (now or time.time())
    except (TypeError, ValueError):
        stamp = now or time.time()
    body = _text_of(message)
    audio = _attachments(message, save_dir)
    haystack = f"{subject} {body}".lower()
    if audio or any(word in haystack for word in VOICE_WORDS):
        kind = "voicemail"
    elif any(word in haystack for word in SMS_WORDS):
        kind = "sms"
    else:
        kind = "email"
    peer = _peer(subject, body, from_header)
    provider_hint = None
    haystack_full = f"{subject} {body} {from_header}".lower()
    for hint, marker in (("voip.ms", "voip.ms"), ("anveo", "anveo"), ("flowroute", "flowroute"),
                         ("signalwire", "signalwire"), ("questblue", "questblue"), ("bulkvs", "bulkvs")):
        if marker in haystack_full:
            provider_hint = hint
            break
    item = {
        "id": "mail:" + hashlib.sha256(f"{subject}{from_header}{stamp}".encode()).hexdigest()[:16],
        "channel": "voicemail" if kind == "voicemail" else "sms",
        "direction": "inbound",
        "sender": peer,
        "recipient": _peer(str(message.get("To") or "")),
        "subject": subject or None,
        "body": body.strip()[:4000] or None,
        "at": int(stamp),
        "thread": peer,
        "reply_to": from_header or None,
        "raw": {"from": from_header, "subject": subject, "kind_hint": kind, "provider": provider_hint},
        "kind": kind,
        "audio": audio[0] if audio else None,
        "from_header": from_header or None,
        "provider_hint": provider_hint,
        "verified": False,
    }
    return item


def sidecar_for(item, path=None):
    """write the <name>.json the voicemail view reads, next to the audio it belongs to."""
    audio = item.get("audio") or {}
    if not audio.get("path"):
        return None
    target = pathlib.Path(audio["path"]).with_suffix(".json")
    note = {"from": item.get("sender"), "at": item.get("at"), "seconds": None,
            "transcript": item.get("body") if item.get("body") and item.get("body") != item.get("subject") else None,
            "source": "forwarded email", "provider": item.get("provider_hint")}
    target.write_text(json.dumps(note, indent=2, sort_keys=True))
    return str(target)
