"""one envelope, many carriers. the umbrella's only real idea.

each folder at the branch root is a lane: it knows its own carrier, its own gate
and its own honest state. this module is what they have in common - the shape a
message has after it arrives, the refusal list nobody may improvise around, and
the rule that unset credentials close a lane instead of opening it.

state values, defined once and used everywhere:
  verified  tested live, with the evidence named
  designed  the shape exists, nothing has run
  closed    credentials unset. unset is closed, never open
  refused   a real blocker stands and wiring will not remove it
"""
import os

KEYS = ("id", "channel", "direction", "sender", "recipient", "subject",
        "body", "at", "thread", "reply_to", "raw")

REFUSED = {
    "otp-by-did": "a voip did is refused as a verification channel, so no lane may promise otherwise",
    "sms-over-sip": "carriers do not hand texts to a sip endpoint; texts arrive as provider events",
    "group-reply": "a group is never whitelisted: the agent answers people who asked it, not a room that did not",
    "social-reply": "a monitoring lane with a mouth is a spam bot; watching is intake, replying is a human decision",
    "api-for-free": "no official api and no paid access means no lane, not a scraper wearing borrowed cookies",
}

RULES = [
    "unset credentials close a lane, they never open it",
    "a config file is not proof; a lane is proven by one real message",
    "renders, never publishes, except streaming where the human presses go live",
]


def envelope(channel, **fields):
    """the one shape. unknown fields stay in raw rather than being dropped."""
    known = {k: fields.pop(k, None) for k in KEYS[1:] if k in fields}
    known.setdefault("direction", "inbound")
    known.setdefault("raw", fields or None)
    known["channel"] = channel
    known["id"] = known.get("id") or f"{channel}:{known.get('at')}:{str(known.get('sender'))[:32]}"
    return {"id": known.pop("id"), **{k: known.get(k) for k in KEYS if k != "id"}}


def gates(spec):
    g = spec.get("gate") or ()
    return (g,) if isinstance(g, str) else tuple(g)


def state_for(spec, env=None):
    """closed when the gate is unset. a lane nobody opened is not 'ready'."""
    env = env if env is not None else os.environ
    if spec.get("state") == "refused":
        return {"lane": spec.get("name"), "state": "refused", "why": spec.get("evidence")}
    missing = [g for g in gates(spec) if not env.get(g)]
    if missing:
        return {"lane": spec.get("name"), "state": "closed", "missing": missing,
                "why": "credentials unset. unset is closed, never open"}
    return {"lane": spec.get("name"), "state": spec.get("state", "designed"),
            "evidence": spec.get("evidence")}
