"""calle: the hosted rail, as a client for the one contract it publishes.

what call-e open sources is its integration layer (the cli, the sdks, the openapi file, all MIT), and
the dialler behind api.heycall-e.com is theirs and hosted. so this module is a client and nothing more:
it never places a call itself, it asks a service that does, with a key the owner brought and credits the
owner pays for. that is the opposite of the rest of this folder, which rings from this machine, and the
readme says so beside the table that sets the two rails next to each other.

the contract is read from their `calle.openapi.yaml` and their python sdk, and one fact in it is easy to
get wrong: `POST /v2/calls` takes the agentic request (a flat `phone`, and a required closed result
schema), not the older `recipients` task that the same file also describes. building the older shape
would be rejected by a strict server, so the request here is the flat one.

stdlib only. the sdk needs httpx and this repo depends on nothing, so the three calls it makes are
written over urllib. every function takes an `opener`, which is how the whole thing is tested without a
key, a network or a single credit.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.heycall-e.com"
KEY_ENV = "CALLE_API_KEY"
BASE_ENV = "CALLE_API_BASE"

PHONE = re.compile(r"\+[1-9][0-9]{7,14}")
REGION = re.compile(r"[A-Z]{2}")

# the closed flat profile the hosted service accepts for a result. anything richer would be accepted by
# our local validator and refused by theirs, after a key was spent, so it is refused here first.
MAX_FIELDS = 32
SCALARS = ("string", "boolean", "integer", "number")

STATUS = ("queued", "in_progress", "completed", "failed", "canceled")
RESULT_STATUS = ("pending", "available", "unavailable", "not_applicable")
ERROR_CODES = ("call_failed", "timed_out", "result_invalid", "result_failed")

# what a status means for the caller: whether to keep waiting
TERMINAL = ("completed", "failed", "canceled")


def key(environ=None):
    """the key lives in the environment, never in a flag, so it cannot end up in a shell history."""
    return str((environ if environ is not None else os.environ).get(KEY_ENV) or "").strip()


def base(environ=None):
    return str((environ if environ is not None else os.environ).get(BASE_ENV) or BASE).rstrip("/")


def gate(environ=None):
    """the same consent the other rail has: a spending call needs HEYPHONY_CALL=allowed AND a key."""
    environ = environ if environ is not None else os.environ
    missing = []
    if str(environ.get("HEYPHONY_CALL") or "").lower() != "allowed":
        missing.append({"needs": "HEYPHONY_CALL=allowed",
                        "why": "a hosted call rings a stranger's phone and spends credits, so the gate "
                               "that guards the other dialling rail guards this one too"})
    if not key(environ):
        missing.append({"needs": KEY_ENV,
                        "why": "the hosted service is called with the owner's own key. there is no shared "
                               "key in this repo, and none is read from a flag"})
    return {"closed": bool(missing), "missing": missing}


def schema_problems(schema):
    """the closed flat profile, checked before a key is spent.

    this is stricter than the local rail's subset on purpose: the hosted service rejects nested objects,
    arrays, null values, combinators and an open `additionalProperties`, and it rejects them after
    accepting the request, which is the expensive place to find out.
    """
    problems = []
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return [{"needs": "schema", "why": "the result is one object, because a call has fields"}]
    if schema.get("additionalProperties") is not False:
        problems.append({"needs": "schema", "unsupported": "additionalProperties",
                         "why": "the hosted profile is closed: additionalProperties must be false"})
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        problems.append({"needs": "schema", "unsupported": "properties",
                         "why": "a result with no fields cannot answer anything"})
        return problems
    if len(properties) > MAX_FIELDS:
        problems.append({"needs": "schema", "unsupported": "size",
                         "why": f"at most {MAX_FIELDS} fields, and this has {len(properties)}"})
    text = json.dumps(schema)
    for feature in ("$ref", "oneOf", "anyOf", "allOf", "not", "patternProperties"):
        if f'"{feature}"' in text:
            problems.append({"needs": "schema", "unsupported": feature,
                             "why": "schema combinators are not part of the hosted profile"})
    for name, spec in properties.items():
        kind = (spec or {}).get("type") if isinstance(spec, dict) else None
        if kind not in SCALARS:
            problems.append({"needs": "schema", "field": name, "unsupported": kind or "type",
                             "why": f"{name} must be one of {list(SCALARS)}: nested objects, arrays and "
                                    "null are not supported by the hosted profile"})
    return problems


def request_body(goal, phone, schema, region=None, locale=None, metadata=None, webhook_url=None,
                 notes=None):
    """the flat agentic request. optional fields are left out rather than sent as null."""
    task = str(goal or "").strip()
    if notes:
        task = f"{task}\n\ncontext: {str(notes).strip()}"
    body = {"task": task, "phone": phone, "result_schema": schema,
            "region": region, "locale": locale, "metadata": metadata, "webhook_url": webhook_url}
    return {k: v for k, v in body.items() if v is not None}


def problems(goal, phone, schema, region=None):
    """everything wrong with a request, found before the network is touched."""
    found = []
    if not str(goal or "").strip():
        found.append({"needs": "goal", "flag": "--goal", "why": "a call without a goal is a wrong number"})
    if not PHONE.fullmatch(str(phone or "")):
        found.append({"needs": "phone", "flag": "--to",
                      "why": "one recipient in e164: a plus, then 8 to 15 digits"})
    if region is not None and not REGION.fullmatch(str(region)):
        found.append({"needs": "region", "why": "two capital letters, like GB, or leave it out"})
    if schema is None:
        found.append({"needs": "schema", "flag": "--schema",
                      "why": "the hosted service requires a result schema, and so does asking at all"})
    else:
        found.extend(schema_problems(schema))
    return found


def idempotency_key(goal, phone, schema, salt=""):
    """stable for the same request, so a retry after a timeout cannot place a second call."""
    import hashlib
    digest = hashlib.sha256(json.dumps([goal, phone, schema, salt], sort_keys=True).encode())
    return "heyphony-" + digest.hexdigest()[:32]


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _path(call_id):
    """the sdk quotes everything and spells a dot out, so an id can never walk the path."""
    return "/v2/calls/" + urllib.parse.quote(str(call_id), safe="").replace(".", "%2E")


def request(method, path, body=None, headers=None, environ=None, opener=None, timeout=30.0):
    """one call to the service. returns parsed json, or raises ApiError with the service's own code."""
    url = base(environ) + path
    data = json.dumps(body).encode() if body is not None else None
    head = {"Authorization": f"Bearer {key(environ)}", "Accept": "application/json"}
    if data is not None:
        head["Content-Type"] = "application/json"
    head.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=head)
    open_ = opener or urllib.request.urlopen
    try:
        with open_(req, timeout=timeout) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as error:
        raise _api_error(error.code, error.read()) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ApiError(0, "connection", f"the request never got a response: {error}") from None
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise ApiError(0, "not_json", "the service answered with something that is not json") from None
    if not isinstance(payload, dict):
        raise ApiError(0, "not_object", "the service answered with a json value that is not an object")
    return payload


def _api_error(status, raw):
    try:
        envelope = json.loads(raw or b"{}")
    except ValueError:
        envelope = {}
    error = envelope.get("error") if isinstance(envelope, dict) else None
    error = error if isinstance(error, dict) else {}
    return ApiError(status, error.get("code") if isinstance(error.get("code"), str) else "internal_error",
                    error.get("message") if isinstance(error.get("message"), str)
                    else "the hosted service refused the request",
                    error.get("details") if isinstance(error.get("details"), dict) else {})


def create(goal, phone, schema, idem, region=None, locale=None, metadata=None, webhook_url=None,
           notes=None, environ=None, opener=None):
    body = request_body(goal, phone, schema, region, locale, metadata, webhook_url, notes)
    return request("POST", "/v2/calls", body, {"Idempotency-Key": idem}, environ, opener)


def get(call_id, environ=None, opener=None):
    return request("GET", _path(call_id), environ=environ, opener=opener)


def cancel(call_id, environ=None, opener=None):
    return request("POST", _path(call_id) + "/cancel", environ=environ, opener=opener)


def wait(call_id, interval=2.0, timeout=600.0, environ=None, opener=None, clock=time.monotonic,
         sleep=time.sleep):
    """poll only while the business result is pending, which is the one signal the contract gives.

    `status` can read completed while the result is still being extracted, so the stop condition is
    `result_status`, not `status`. a deadline returns the last snapshot with the call id attached, so a
    long call is a thing the caller can resume by id rather than a lost one.
    """
    deadline = clock() + timeout
    last = None
    while clock() <= deadline:
        last = get(call_id, environ, opener)
        if last.get("result_status") != "pending":
            return last, False
        sleep(interval)
    return last, True


def shape(call, via="calle"):
    """the hosted snapshot in the one shape both rails return, so a caller reads a single dialect."""
    call = call if isinstance(call, dict) else {}
    transcript = [{"offset_seconds": t.get("offset_seconds"), "speaker": t.get("speaker"),
                   "text": t.get("text")} for t in (call.get("transcript") or []) if isinstance(t, dict)]
    return {
        "via": via,
        "id": call.get("id"),
        "status": call.get("status"),
        "call_outcome": call.get("call_outcome"),
        "result_status": call.get("result_status"),
        "result": call.get("result"),
        "error": call.get("error"),
        "transcript": transcript,
        "billing_call_id": call.get("call_id"),
        "completed_at": call.get("completed_at"),
    }
