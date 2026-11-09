"""how each provider's texts actually reach us.

five number shops, five different hooks, and the difference is not cosmetic. one
forwards an email, one signs a json webhook, one calls a url with the message
spliced into the query string, one posts to a url you set over its api, and the
trunk provider needs the setting applied per number before anything arrives at
all. this module is where that is data rather than instructions in a readme,
because the catcher has to parse five shapes and the cli has to be able to say
which url to paste and, where an api exists, to set it for you.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

from src import providers

BASE = "https://<host>:8098"


def pick(payload, keys, depth=0):
    """walk a payload for the first of these keys, so a nested shape still parses."""
    if not isinstance(payload, dict) or depth > 3:
        return None
    for k in keys:
        if payload.get(k) not in (None, ""):
            return payload[k]
    for value in payload.values():
        if isinstance(value, dict):
            found = pick(value, keys, depth + 1)
            if found not in (None, ""):
                return found
    return None


ROUTES = {
    "voip.ms": {
        "kind": "email",
        "path": None,
        "configure": ["in the portal, enable sms on the number and set sms to email",
                      "point that email at the email lane, not at the sip client: texts never ride sip"],
        "apply": None,
        "evidence": "carrier feature described on voip.ms; no message has been received",
    },
    "flowroute": {
        "kind": "webhook-json",
        "path": "/sms/flowroute",
        "parse": {"sender": ["from"], "recipient": ["to"], "body": ["body"], "id": ["id", "message_id"],
                  "at": ["timestamp"]},
        "configure": ["arm an inbound sms route on the number in the portal",
                      "paste the url below as its destination, and allowlist the host by ip if asked"],
        "apply": None,
        "evidence": "flowroute documents http api or smpp delivery, never sip",
    },
    "anveo": {
        "kind": "url-forward",
        "path": "/sms/anveo",
        "query": "from=$[from]$&to=$[to]$&message=$[message]$",
        "parse": {"sender": ["from"], "recipient": ["to"], "body": ["message", "body"], "id": [], "at": []},
        "configure": ["open the number's sms options in the portal and tick forward to url",
                      "paste the url below: anveo replaces the placeholders with the real values",
                      "do not enable sms over sip: anveo ignores registration for sms delivery and needs a "
                      "fully qualified host with a port, and it passes the text in x-anveo-sms-* headers"],
        "apply": {"module": "anveo", "method": "DID.UPDATE",
                  "auth": ["ANVEO_EMAIL", "ANVEO_SECURE_PHRASE"],
                  "headers": {"userkey": "ANVEO_USERKEY"},
                  "why": "DID.UPDATE sets SMS_URL by e164, so the hook is a call and not a portal visit"},
        "evidence": "anveo's own receive-sms-over-http page and did.update arguments",
    },
    "signalwire": {
        "kind": "webhook-json",
        "path": "/sms/signalwire",
        "parse": {"sender": ["from"], "recipient": ["to"], "body": ["body"], "id": ["message_id"],
                  "at": ["timestamp"]},
        "configure": ["set the number's message handler to this url in the dashboard, or over fabric rest",
                      "the payload is {\"message\": {...}} with from, to, body, message_id and timestamp inside"],
        "apply": {"method": "dashboard or fabric rest", "why": "the number's handler resource path is not verified here"},
        "evidence": "signalwire's swml inbound message webhook payload, read from their docs",
    },
    "questblue": {
        "kind": "post-to-url",
        "path": "/sms/questblue",
        "method": "json",
        "parse": {"sender": ["from"], "recipient": ["to"], "body": ["msg", "body"], "id": [], "at": []},
        "configure": ["set the number's sms mode to url, with this url as the target",
                      "choose the post method: form, json or xml. this lane asks for json",
                      "the posted fields are from, to and msg, and there is no message id, so one is derived from the body"],
        "apply": {"method": "PUT", "url": "https://api.questblue.com/smsv2",
                  "query": {"sms_mode": "url", "post2urlmethod": "json"},
                  "auth": ["QUESTBLUE_API_USER", "QUESTBLUE_API_PASS"],
                  "headers": {"Security-Key": "QUESTBLUE_API_KEY"}},
        "evidence": "questblue's published openapi spec: put /smsv2 with sms_mode=url and post2url",
    },
    "bulkvs": {
        "kind": "webhook-json",
        "path": "/sms/bulkvs",
        "parse": {"sender": ["from", "From", "OriginationNumber", "Source"],
                  "recipient": ["to", "To", "Destination"],
                  "body": ["message", "Message", "Body", "Text"],
                  "id": ["RefId", "refid", "id"],
                  "at": ["timestamp", "Time"]},
        "configure": ["register one webhook for messaging over the api, described below",
                      "then set Sms (and Mms if wanted) plus the same webhook on the number record",
                      "the posted field names are not written down anywhere we could read, so an unknown body is stored raw "
                      "rather than dropped: the first real text teaches us the shape"],
        "apply": {"method": "PUT", "url": "https://portal.bulkvs.com/api/v1.0/webHooks",
                  "json": {"Webhook": "comms", "Description": "comms inbound sms", "Url": "@paste",
                           "Dlr": True, "Method": "POST"},
                  "auth": ["BULKVS_API_USER", "BULKVS_API_PASS"],
                  "why": "one url, registered once, then attached to numbers"},
        "evidence": "bulkvs's own openapi spec: put /webHooks and the Webhook field on /tnRecord",
    },
    "jmp.chat": {
        "kind": "xmpp",
        "path": None,
        "parse": {"sender": ["from", "sender"], "recipient": ["to"], "body": ["body", "message"],
                  "id": ["id"], "at": ["timestamp"]},
        "configure": ["run a jabber client on the host and stay signed in: jmp delivers texts and voicemail "
                      "transcriptions as chat messages to your jid",
                      "there is no url to paste and no webhook to arm, which is the whole difference: the "
                      "receiver is a client, not a route",
                      "a bridge from that client into the inbox is this lane's next piece of work, not a setting"],
        "apply": None,
        "evidence": "jmp.chat's own faq and pricing: a us or canadian number, texts and picture messages over any jabber app, "
                    "voicemail as audio plus transcription",
    },
    "voyced": {
        "kind": "none",
        "path": None,
        "configure": ["nothing to paste: no sms is advertised on a geographic number",
                      "voice arrives at the sip registration like every other number here"],
        "apply": None,
        "evidence": "voyced's store prices geographic dids per country and bills inbound per minute; no sms claim found",
    },
    "voxacall": {
        "kind": "none",
        "path": None,
        "configure": ["nothing to paste: an api is advertised behind registration but no sms story is public",
                      "and a no-kyc trunk is the first thing a recipient's risk engine blocks"],
        "apply": None,
        "evidence": "voxacall.me describes no-kyc sip trunking and dids paid in bitcoin or usdt, with a developer api behind login",
    },
    "bitcall": {
        "kind": "none",
        "path": None,
        "configure": ["nothing to paste yet: their integration guides list inbound numbers as coming soon",
                      "the documented api is otp, esim and hlr, which is not an inbox"],
        "apply": None,
        "evidence": "docs.bitcall.io covers otp, esim and hlr; the retell and vapi guides say inbound dids are on the roadmap",
    },
}


def _key(name):
    key = str(name or "").lower().replace("voipms", "voip.ms").strip()
    if key not in ROUTES:
        raise KeyError(f"no route for provider: {name}. known: {', '.join(ROUTES)}")
    return key


def paste_url(provider, base=BASE):
    """the exact string a person pastes into a provider's box."""
    key = _key(provider)
    route = ROUTES[key]
    if not route["path"]:
        return None
    url = f"{base.rstrip('/')}{route['path']}"
    if route.get("query"):
        return f"{url}?{route['query']}"
    return url


def hook(provider, base=BASE, did=None):
    """everything needed to make one provider's texts land: paste, configure, apply."""
    key = _key(provider)
    route = ROUTES[key]
    profile = providers.profile(key)
    call = None
    if route.get("apply"):
        apply = route["apply"]
        call = dict(apply)
        call["ready"] = _ready(apply)
        if apply.get("url"):
            call["as_curl"] = _curl(apply, paste_url(key, base), did)
    return {"provider": key,
            "kind": route["kind"],
            "path": route["path"],
            "paste_url": paste_url(key, base),
            "sip_style": profile["sip_style"],
            "configure": route["configure"],
            "apply": call,
            "cli": f"heyphony hooks {key} --base {base.rstrip('/')}",
            "verified": False,
            "evidence": route["evidence"],
            "needs": "one real text, stored by the catcher, before any of this is more than designed"}


def _env_names(apply):
    names = list(apply.get("auth") or [])
    names += [v for v in (apply.get("headers") or {}).values()]
    return names


def _ready(apply):
    return all(os.environ.get(name) for name in _env_names(apply))


def _payload(apply, paste, did):
    query = {k: (paste if v == "@paste" else v) for k, v in (apply.get("query") or {}).items()}
    if query:
        query.setdefault("did", did or "+1...")
        if apply.get("url", "").endswith("/smsv2"):
            query["post2url"] = paste
    body = json.loads(json.dumps(apply.get("json") or {}))
    for field, value in list(body.items()):
        if value == "@paste":
            body[field] = paste
    return query, body


def _curl(apply, paste, did=None):
    query, body = _payload(apply, paste, did)
    auth = apply.get("auth") or []
    parts = ["curl"]
    if auth:
        parts.append(f'-u "${auth[0]}:${auth[1] if len(auth) > 1 else auth[0] + "_PASS"}"')
    for header, env in (apply.get("headers") or {}).items():
        parts.append(f'-H "{header}: ${env}"')
    if body:
        parts.append("-H \"content-type: application/json\"")
        parts.append("-d '" + json.dumps(body) + "'")
    url = apply["url"] + (("?" + urllib.parse.urlencode(query)) if query else "")
    parts.append(f'-X {apply["method"]} "{url}"')
    return " ".join(parts)


# when a carrier carries a real group thread, the thread has a name of its own and the reply belongs
# to it rather than to whoever typed last. none of the ten paths wired today publishes one of these
# fields, so this list is what a carrier with group mms would land in without a code change.
THREAD_KEYS = ("thread", "thread_id", "threadId", "group_id", "groupId", "conversation_id",
               "conversationId", "message_thread_id", "chat_id", "chatId")
PARTICIPANT_KEYS = ("participants", "recipients", "to_participants", "group_members", "members")


def normalize(provider, payload):
    """one envelope out of every shape. a shape nobody predicted is still stored."""
    key = _key(provider)
    if ROUTES[key]["kind"] in ("none", "xmpp"):
        # nothing arrives by post from these, so a payload here is a surprise worth keeping whole
        return {"id": f"{key}:unexpected", "channel": "sms", "direction": "inbound", "sender": None,
                "recipient": None, "subject": None, "body": None, "at": int(time.time()),
                "thread": None, "reply_to": None, "raw": payload}
    parse = ROUTES[key].get("parse") or {}
    thread = pick(payload, (parse.get("thread") or []) + list(THREAD_KEYS))
    participants = pick(payload, (parse.get("participants") or []) + list(PARTICIPANT_KEYS))
    if isinstance(participants, str):
        participants = [part.strip() for part in participants.split(",") if part.strip()]
    if not isinstance(participants, list):
        participants = None
    sender = pick(payload, parse.get("sender") or ["from", "source"])
    recipient = pick(payload, parse.get("recipient") or ["to", "destination"])
    body = pick(payload, parse.get("body") or ["body", "text", "message"])
    at = pick(payload, parse.get("at") or ["timestamp", "at"]) or int(time.time())
    ident = pick(payload, parse.get("id") or ["id", "message_id"])
    if not ident:
        digest = hashlib.sha256(json.dumps([sender, recipient, body, at], sort_keys=True).encode())
        ident = f"{key}:{digest.hexdigest()[:16]}"
    return {"id": ident, "channel": "sms", "direction": "inbound", "sender": sender,
            "recipient": recipient, "subject": None, "body": body, "at": at,
            "thread": str(thread) if thread not in (None, "") else None,
            "participants": participants, "reply_to": None, "raw": payload}


def apply_hook(provider, base=BASE, did=None):
    """arm the hook over the provider's own api, when that is a documented call we can make."""
    key = _key(provider)
    route = ROUTES[key]
    apply = route.get("apply")
    if not apply or (not apply.get("url") and not apply.get("module")):
        return {"applied": False, "provider": key,
                "why": "this provider's route is set by hand, or there is no route to set"}
    paste = paste_url(key, base)
    if apply.get("module") == "anveo":
        from src.setup import provision
        if not did:
            return {"applied": False, "provider": key,
                    "why": "anveo arms one number at a time, so pass --did",
                    "as_curl": provision.as_curl("DID.UPDATE", {"FILTER.E164": "<did>", "SMS_URL": paste})}
        answer = provision.arm_sms(did, paste)
        if answer.get("ok"):
            return {"applied": True, "provider": key, "result": answer.get("result"),
                    "did": did, "sms_url": paste}
        return {"applied": False, "provider": key, "missing": answer.get("missing"),
                "why": answer.get("why"), "as_curl": answer.get("as_curl")}
    query, body = _payload(apply, paste, did)
    if not _ready(apply):
        return {"applied": False, "provider": key, "missing": [n for n in _env_names(apply) if not os.environ.get(n)],
                "why": "no credentials in the environment, so nothing was sent",
                "as_curl": _curl(apply, paste, did)}
    url = apply["url"] + (("?" + urllib.parse.urlencode(query)) if query else "")
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(url, data=data, method=apply["method"])
    if data:
        request.add_header("Content-Type", "application/json")
    auth = apply.get("auth") or []
    if auth:
        import base64
        pair = f"{os.environ[auth[0]]}:{os.environ[auth[1]] if len(auth) > 1 else ''}"
        request.add_header("Authorization", "Basic " + base64.b64encode(pair.encode()).decode())
    for header, env in (apply.get("headers") or {}).items():
        request.add_header(header, os.environ[env])
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            return {"applied": True, "provider": key, "status": answer.status,
                    "body": answer.read().decode("utf-8", "replace")[:400]}
    except Exception as exc:  # the provider's answer is the useful part, not our traceback
        return {"applied": False, "provider": key, "why": f"the provider refused: {exc}"}
