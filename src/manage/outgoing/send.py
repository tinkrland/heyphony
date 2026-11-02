"""outbound: one message, when somebody asked for it, and never a list.

the lane was drafts only until now, and the reason was the right one: sending is the half of telephony
where a mistake is a person's phone buzzing, and a rail improvised for a demo is a rail that eventually
sends something nobody meant. this file is the deliberate version.

what it will not do, in the order the checks run:

- **one recipient.** a comma, a list or a loop is refused here rather than documented as discouraged.
  a campaign is a different product with consent, attestation and a registered business behind it, and
  no flag on this command turns it into one.
- **nothing sends unless the gate is open and the caller said so.** `HEYPHONY_SEND=allowed` in the
  environment, plus `allow=True` from the command line. either one alone produces a draft, with the
  exact request printed so it can be read before it is real.
- **nothing sends to a provider with no documented send path.** the refusals name the providers that
  do have one rather than failing somewhere deeper with a 404.
- **nothing sends with half credentials.** a missing env var is a refusal that names it, not a request
  that authenticates as nobody.
- **nothing long.** 1600 characters is the ceiling, because past that it stopped being a message to a
  person and became something else, and this rail only knows how to do the first one.

the operator owns the rest. provider terms, consent, quiet hours and what the recipient agreed to are
theirs to comply with, and the honest position is that a tool which respects a gate cannot also audit a
business. that is why the gate is a decision and not a warning.

verified: the endpoints and payload shapes are from each provider's own documentation, linked in the
table below. unverified: no message has been sent through this rail, so status codes are expectations
rather than observations. the first real one should go to your own phone.
"""
import base64
import json
import math
import os
import shlex
import time
import urllib.parse
import urllib.request
import uuid

from src.manage import inbox

GATE = "HEYPHONY_SEND"
GATE_OPEN = "allowed"
MAX_CHARS = 1600
GSM = set(" !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ"
          "[\\]^_abcdefghijklmnopqrstuvwxyz{|}~\n\r")


def sender(provider):
    """the provider's documented outbound path, or None. refusals name what exists rather than guess."""
    return SENDERS.get(provider)


SENDERS = {
    "voip.ms": {
        "provider": "voip.ms",
        "method": "GET",
        "url": "https://voip.ms/api/v1/rest.php",
        "auth": ["VOIPMS_API_USER", "VOIPMS_API_PASS"],
        "docs": "https://voip.ms/m/api.php",
        "success": (200,),
        "note": "rest.php with method=sendSMS; the did must be sms capable on the sub account holding the api key",
        "verified": False,
    },
    "flowroute": {
        "provider": "flowroute",
        "method": "POST",
        "url": "https://api.flowroute.com/v2.2/messages",
        "auth": ["FLOWROUTE_API_KEY", "FLOWROUTE_API_SECRET"],
        "docs": "https://developer.flowroute.com/docs/",
        "success": (200, 202),
        "note": "basic auth with the api key as the user and the secret as the password",
        "verified": False,
    },
    "signalwire": {
        "provider": "signalwire",
        "method": "POST",
        "url": "https://{space}.signalwire.com/api/laml/2010-04-01/Accounts/{project}/Messages.json",
        "auth": ["SIGNALWIRE_SPACE", "SIGNALWIRE_PROJECT", "SIGNALWIRE_TOKEN"],
        "docs": "https://signalwire.com/docs",
        "success": (200, 201),
        "note": "the laml messages resource, form encoded, project id as the basic auth user",
        "verified": False,
    },
}


def segments(text):
    """how many messages a body costs. gsm 7 bit is 160, and 153 per part once it splits."""
    text = str(text or "")
    extended = any(character not in GSM for character in text)
    if extended:
        size, part = 70, 67
    else:
        size, part = 160, 153
    count = 1 if len(text) <= size else math.ceil(len(text) / part)
    return {"chars": len(text), "segments": count, "encoding": "ucs2" if extended else "gsm7",
            "bytes_max": size}


def one_recipient(to):
    """true for a single e164 number. anything with a separator is somebody trying to send a list."""
    text = str(to or "").strip()
    if not text.startswith("+") or not text[1:].isdigit():
        return False
    return len(text) in range(8, 17)


def request_for(provider, from_number, to, text):
    """the request, built and readable, with no side effect. this is what a draft prints."""
    row = sender(provider)
    if row is None:
        raise KeyError(provider)
    missing = [name for name in row["auth"] if not os.environ.get(name)]
    if missing:
        raise ValueError("missing credentials: " + ", ".join(missing))
    env = os.environ

    if provider == "voip.ms":
        query = urllib.parse.urlencode({
            "api_username": env["VOIPMS_API_USER"], "api_password": env["VOIPMS_API_PASS"],
            "method": "sendSMS", "did": from_number, "dst": to, "message": text})
        return {"method": "GET", "url": f'{row["url"]}?{query}', "headers": {}, "body": None}

    if provider == "flowroute":
        pair = f'{env["FLOWROUTE_API_KEY"]}:{env["FLOWROUTE_API_SECRET"]}'
        body = {"data": {"type": "message", "attributes": {"to": to, "from": from_number,
                                                           "body": text}}}
        return {"method": "POST", "url": row["url"],
                "headers": {"Content-Type": "application/vnd.api+json",
                            "Authorization": "Basic " + base64.b64encode(pair.encode()).decode()},
                "body": json.dumps(body, sort_keys=True)}

    url = row["url"].format(space=env["SIGNALWIRE_SPACE"], project=env["SIGNALWIRE_PROJECT"])
    pair = f'{env["SIGNALWIRE_PROJECT"]}:{env["SIGNALWIRE_TOKEN"]}'
    body = urllib.parse.urlencode({"From": from_number, "To": to, "Body": text})
    return {"method": "POST", "url": url,
            "headers": {"Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": "Basic " + base64.b64encode(pair.encode()).decode()},
            "body": body}


def as_curl(request):
    """the request as one readable line. credentials are named, never printed: a draft gets pasted."""
    parts = ["curl -sS", "-X", request["method"]]
    for name, value in sorted(request["headers"].items()):
        if name.lower() == "authorization":
            value = value.split(" ", 1)[0] + " <credentials>"
        parts += ["-H", shlex.quote(f"{name}: {value}")]
    url = request["url"]
    if "api_password=" in url:
        head, tail = url.split("api_password=", 1)
        url = f"{head}api_password=<set>&" + (tail.split("&", 1)[1] if "&" in tail else "")
    parts.append(shlex.quote(url))
    if request.get("body"):
        parts += ["-d", shlex.quote(request["body"])]
    return " ".join(parts)


# the ten providers the repo knows about, and what each one's outbound story actually is. three are
# wired above; the rest are named here rather than left to a generic refusal, because "that provider
# does not work" and "the parameter names for that gateway are behind a portal" are different
# sentences and only one of them is a bug.
PATHS = {
    "voip.ms": {"state": "wired", "docs": "https://voip.ms/m/api.php",
                "why": "rest.php with method=sendSMS, one call per message"},
    "flowroute": {"state": "wired", "docs": "https://developer.flowroute.com",
                  "why": "POST /v2.2/messages, json api envelope, basic auth"},
    "signalwire": {"state": "wired", "docs": "https://signalwire.com/docs",
                   "why": "laml Messages.json per space, form body, basic auth"},
    "anveo": {"state": "gateway not wired", "docs": "https://www.anveo.com/api.asp",
              "why": "anveo publishes an sms http gateway and the parameter names sit behind their "
                     "api portal, so guessing them is the one thing this repo refuses to do. paste "
                     "the gateway url from the account page and it is a ten line addition"},
    "questblue": {"state": "gateway not wired", "docs": "https://docs.questblue.com",
                  "why": "smsv2 is documented for inbound delivery, and the outbound call lives in "
                         "their portal docs rather than on a page this repo could read"},
    "bulkvs": {"state": "gateway not wired",
               "docs": "https://portal.bulkvs.com/api/v1.0/documentation",
               "why": "their api reference renders behind a login, so the message fields are unread "
                      "from here"},
    "jmp.chat": {"state": "no http path", "docs": "https://jmp.chat",
                 "why": "texts travel as xmpp messages to your jid, so there is no http send to call "
                        "and no sip to register. it is a real lane, and not this one"},
    "voyced": {"state": "no outbound sms claim", "docs": "https://voyced.eu",
               "why": "their api is in controlled testing and no outbound sms is claimed"},
    "voxacall": {"state": "no outbound sms claim", "docs": "https://voxacall.me",
                 "why": "sip trunking with no public sms api"},
    "bitcall": {"state": "no outbound sms claim", "docs": "https://docs.bitcall.io",
                "why": "their api is otp, esim and hlr lookups, and inbound dids are still coming soon"},
}


def path_index():
    """every provider this repo knows, with its outbound state, so nothing is silently unsupported."""
    return {name: dict(row) for name, row in PATHS.items()}


def path_state(provider):
    """what this provider's outbound story is, or None for a name the repo has never heard of."""
    return PATHS.get(provider)


def _http(request):
    """the only place a request actually leaves. returns (status, body text)."""
    data = request["body"].encode() if request.get("body") else None
    opener = urllib.request.Request(request["url"], data=data, method=request["method"],
                                    headers=request["headers"])
    try:
        with urllib.request.urlopen(opener, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def draft(provider, from_number, to, text, why):
    """a draft is the request plus the reason it did not leave. it stores nothing."""
    try:
        request = request_for(provider, from_number, to, text)
    except (KeyError, ValueError) as error:
        return {"sent": False, "drafted": False, "provider": provider, "why": str(error),
                "providers_with_a_send_path": sorted(SENDERS)}
    return {"sent": False, "drafted": True, "provider": provider, "from": from_number, "to": to,
            "segments": segments(text), "why": why, "curl": as_curl(request),
            "docs": sender(provider)["docs"], "note": sender(provider)["note"]}


def send(provider, from_number, to, text, allow=False, store=True, path=None, opener=None):
    """place one message, or explain exactly why not. returns a dict that always says which happened."""
    text = "" if text is None else str(text)
    gate = os.environ.get(GATE, "").strip().lower()

    if not one_recipient(from_number):
        return {"sent": False, "why": "the sender must be one e164 number: the did this provider holds",
                "got": from_number}
    if not one_recipient(to):
        return {"sent": False, "why": "one recipient, in e164, per call",
                "got": to, "rule": "this rail has no way to send a list, on purpose"}
    if sender(provider) is None:
        known = path_state(provider)
        return {"sent": False, "provider": provider,
                "why": (known["why"] if known else "not a provider this repo knows"),
                "state": (known["state"] if known else "unknown"),
                "docs": (known["docs"] if known else None),
                "providers_with_a_send_path": sorted(SENDERS),
                "note": "a provider can receive and still have no send rail wired; that is a refusal, "
                        "not a bug to route around. `heyphony send --paths` lists all of them"}
    if len(text) > MAX_CHARS:
        return {"sent": False, "why": f"over {MAX_CHARS} characters is not a text to a person",
                "chars": len(text)}
    if not text.strip():
        return {"sent": False, "why": "empty body"}
    if not gate:
        return draft(provider, from_number, to, text,
                     f"nothing sent: {GATE} is not set to {GATE_OPEN!r}")
    if gate != GATE_OPEN:
        return {"sent": False, "why": f"{GATE} is {gate!r}, and only {GATE_OPEN!r} opens the rail"}
    if not allow:
        return draft(provider, from_number, to, text,
                     "nothing sent: the gate is open, but this call did not ask to send")
    try:
        request = request_for(provider, from_number, to, text)
    except ValueError as error:
        return {"sent": False, "provider": provider, "why": str(error),
                "note": "the environment is missing a credential, so nothing was half configured"}

    status, body = (opener or _http)(request)
    expected = sender(provider)["success"]
    ok = status in expected
    answer = {"sent": ok, "provider": provider, "from": from_number, "to": to, "status": status,
              "segments": segments(text), "docs": sender(provider)["docs"]}
    if not ok:
        answer["why"] = "the provider did not accept it"
        answer["body"] = body[:400]
        return answer

    answer["response"] = body[:400]
    if store:
        entry = {"id": "out-" + uuid.uuid4().hex[:16], "channel": "sms", "direction": "out",
                 "sender": from_number, "recipient": to, "body": text, "at": int(time.time()),
                 "raw": {"provider": provider, "status": status, "response": body[:400]}}
        stored, reason = inbox.append(entry, path)
        answer["stored"] = stored
        answer["store_reason"] = reason
    answer["next"] = "one message sent. the thread now holds both halves of the conversation"
    return answer


def reply(provider, from_number, to, text, allow=False, path=None, opener=None):
    """the same rail, named for the case it exists for: answering somebody who wrote first."""
    answer = send(provider, from_number, to, text, allow=allow, path=path, opener=opener)
    answer["reply"] = True
    return answer
