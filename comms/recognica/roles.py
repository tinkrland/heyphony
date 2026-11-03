"""who somebody is to the owner: the owner, a person, or another agent.

this is deliberately the smallest module in the book. there are three answers, one of them is
special, and the mistake worth designing against is assuming. an inbound sender is a person who
wrote to us, not the principal. an entry becomes the owner because somebody said so, once, in
config or in a command, and that decision is stored rather than recomputed from vibes.

the owner can also be seeded from the environment, which is what a host deployment actually has:
RECOGNICA_OWNER_EMAIL and RECOGNICA_OWNER_PHONE, comma separated. if neither is set, there is no
owner yet and the book says so, because an agent with a guessed owner is worse than one with none.
"""
import os

from comms.recognica import cards as cardbook

OWNER_EMAIL = "RECOGNICA_OWNER_EMAIL"
OWNER_PHONE = "RECOGNICA_OWNER_PHONE"
OWNER_NAME = "RECOGNICA_OWNER_NAME"


def _pairs(channel, values):
    for value in str(values or "").split(","):
        value = value.strip()
        if value:
            yield channel, value


def owner_handles(env=None):
    env = env if env is not None else os.environ
    pairs = list(_pairs("email", env.get(OWNER_EMAIL)))
    pairs += list(_pairs("phone", env.get(OWNER_PHONE)))
    pairs += list(_pairs("sms", env.get(OWNER_PHONE)))
    return pairs


def make_owner(cards, handles=None, name=None, env=None):
    """name the owner, once. idempotent: a second call updates rather than adding a second owner."""
    handles = list(handles or []) or owner_handles(env)
    name = name or (env or os.environ).get(OWNER_NAME)
    if not handles and not name:
        return cards, {"ok": False, "why": "no owner handle: pass one, or set RECOGNICA_OWNER_EMAIL/PHONE"}
    existing = [c for c in cards if c.get("role") == cardbook.ROLE_OWNER]
    if existing:
        card = existing[0]
    else:
        card = cardbook.new(name or "owner", kind=cardbook.KIND_HUMAN, role=cardbook.ROLE_OWNER)
        cards = [c for c in cards if c["id"] != card["id"]] + [card]
    for channel, value in handles:
        cards, result = cardbook.link(cards, card["id"], channel, value)
        if not result.get("linked"):
            return cards, {"ok": False, "why": "that handle belongs to another card",
                           "detail": result, "needs": "merge those cards first"}
    card = next(c for c in cards if c["id"] == card["id"])
    card["role"] = cardbook.ROLE_OWNER
    return cards, {"ok": True, "owner": card["id"], "handles": card.get("handles"),
                   "shelf": cardbook.shelf(card)}


def owner(cards):
    return next((c for c in cards if c.get("role") == cardbook.ROLE_OWNER
                 and c.get("kind") != cardbook.KIND_AGENT), None)


def role_of(cards, channel, handle):
    """owner, contact, agent, or unknown. unknown is an answer, not an error."""
    try:
        card = cardbook.owner_of(cards, channel, handle)
    except ValueError:
        return {"role": "unknown", "why": "empty handle"}
    if card is None:
        return {"role": "unknown", "why": "no card holds that handle"}
    if card.get("kind") == cardbook.KIND_AGENT:
        return {"role": "agent", "card": card["id"], "name": card["name"]}
    if card.get("role") == cardbook.ROLE_OWNER:
        return {"role": "owner", "card": card["id"], "name": card["name"]}
    return {"role": "contact", "card": card["id"], "name": card["name"]}


def is_owner(cards, channel, handle):
    return role_of(cards, channel, handle)["role"] == "owner"


def add_agent(cards, name, handles=None, note=""):
    """another agent, on its own shelf. it is somebody the agent may talk to, never the owner."""
    card = cardbook.new(name, handles, note, kind=cardbook.KIND_AGENT)
    cards = [c for c in cards if c["id"] != card["id"]] + [card]
    return cards, {"ok": True, "agent": card["id"], "shelf": cardbook.shelf(card)}


def summary(cards, env=None):
    """one honest paragraph the agent can start a session with."""
    where = cardbook.tree(cards)
    gaps = [name for name in (OWNER_EMAIL, OWNER_PHONE) if not (env or os.environ).get(name)]
    return {**where,
            "knows_owner": where["owner"] is not None,
            "owner_from_env": bool(owner_handles(env)),
            "unset_env": gaps,
            "next": ("set RECOGNICA_OWNER_EMAIL or RECOGNICA_OWNER_PHONE, or run "
                     "`comms recognica --owner email:you@example.com`") if not where["owner"] else None}
