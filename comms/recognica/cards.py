"""the card: one person, every lane, and the conversation they already had.

this module lives under recognica, the contact book, because a card is an entry in somebody's
address book rather than a feature of a catcher. the shelves decide more than storage: an entry
under humans/owner is the person the agent serves, an entry under humans/people is somebody it
talks to, and an entry under agents is a peer that is also software. a single flat list cannot tell
those apart, and delegation means the difference matters more than the message.

the reason this module exists is a small failure everybody has lived through: the same person writes
on email, then on telegram, then on a slack dm, and each arrival lands as a stranger. the agent asks
what was already answered, the human pastes the other chat in, and the whole point of having one
agent collapses into being nine inboxes with one memory.

a card fixes that at the seam rather than in a prompt. it is a small record of a person - a name, the
handles they use per carrier, an optional note - and because every lane produces the same envelope,
a message from any handle resolves to the same card. the digest is then the thing the human was doing
by hand: the last few things said across all of them, in one order.

three rules keep it honest, and they are all about not inventing a person:

a handle belongs to one card. a second card claiming it is a merge, and a merge needs its name typed,
because merging the wrong two people is impersonation with extra steps.
an unknown sender is not a card yet. intake stores the message; nothing about a stranger implies they
are somebody we already know.
a card is state, not a secret, so it lives where the lane lives: on the host, out of the burn lane.
"""
import json
import os
import pathlib
import re
import time

CHANNELS = ("email", "phone", "sms", "imessage", "telegram", "slack", "discord", "whatsapp", "signal")

REFUSED = {
    "silent-merge": "two cards with the same handle is impersonation with extra steps; merge needs its name typed",
    "stranger-card": "an unknown sender is stored, not stitched: being messaged does not make somebody known",
    "group-card": "a group is a room, not a person, so it does not get a card",
}


def _digits(handle):
    return re.sub(r"[^\d+]", "", str(handle))


def canonical(channel, handle):
    """the same person writes their number four ways; one of them has to win."""
    raw = str(handle or "").strip()
    if not raw:
        raise ValueError("empty handle")
    if channel == "email":
        return raw.lower()
    if channel in ("phone", "sms"):
        digits = _digits(raw)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        return digits if digits.startswith("+") else "+" + digits
    if channel == "imessage":
        return raw.lower() if "@" in raw else _digits(raw)
    return raw  # platform ids are exact, and a guessed normalisation loses people


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-") or "card"


KIND_HUMAN = "human"
KIND_AGENT = "agent"
ROLE_OWNER = "owner"
ROLE_CONTACT = "contact"


def new(name, handles=None, note="", now=None, kind=KIND_HUMAN, role=ROLE_CONTACT):
    """a new card is a contact, not the owner. whoever the agent serves is named, never inferred."""
    card = {"id": _slug(name), "name": str(name).strip(), "handles": {}, "note": note,
            "kind": kind, "role": role if kind == KIND_HUMAN else None,
            "created_at": now if now is not None else int(time.time())}
    for channel, values in (handles or {}).items():
        for value in ([values] if isinstance(values, str) else values):
            card["handles"].setdefault(channel, []).append(canonical(channel, value))
    return card


def owner_of(cards, channel, handle):
    """which card already holds this handle, if any. the merge check reads this."""
    want = canonical(channel, handle)
    for card in cards:
        if want in card.get("handles", {}).get(channel, []):
            return card
    return None


def link(cards, card_id, channel, handle):
    """add a handle, or say exactly why not. returns (cards, result)."""
    card = next((c for c in cards if c["id"] == card_id), None)
    if card is None:
        return cards, {"linked": False, "why": f"no card {card_id!r}"}
    want = canonical(channel, handle)
    held = owner_of(cards, channel, want)
    if held is not None:
        if held["id"] == card["id"]:
            return cards, {"linked": True, "already": True, "card": card["id"]}
        return cards, {"linked": False, "why": "silent-merge", "detail": REFUSED["silent-merge"],
                       "held_by": held["id"], "how": f"comms card --merge {card['id']} {held['name']}"}
    card.setdefault("handles", {}).setdefault(channel, []).append(want)
    return cards, {"linked": True, "card": card["id"], "handle": want}


def resolve(cards, channel, handle):
    """the whole point: any lane, one person. an unknown sender resolves to nothing, out loud."""
    try:
        card = owner_of(cards, channel, handle)
    except ValueError:
        return {"card": None, "why": "empty handle"}
    if card is None:
        return {"card": None, "why": "stranger-card", "detail": REFUSED["stranger-card"]}
    return {"card": card["id"], "name": card["name"], "channels": sorted(card.get("handles", {}))}


def merge(cards, keep_id, drop_id, confirm):
    """two cards becoming one, with the dropped card's name typed. never a side effect."""
    keep = next((c for c in cards if c["id"] == keep_id), None)
    drop = next((c for c in cards if c["id"] == drop_id), None)
    if keep is None or drop is None:
        return cards, {"merged": False, "why": "one of those cards does not exist"}
    if str(confirm or "").strip().lower() != drop["name"].strip().lower():
        return cards, {"merged": False, "why": "type the dropped card's name to merge",
                       "detail": REFUSED["silent-merge"], "needs": drop["name"]}
    for channel, values in drop.get("handles", {}).items():
        for value in values:
            if value not in keep.setdefault("handles", {}).setdefault(channel, []):
                keep["handles"][channel].append(value)
    keep["note"] = " / ".join(x for x in (keep.get("note", ""), drop.get("note", "")) if x)
    return [c for c in cards if c["id"] != drop["id"]], {"merged": True, "into": keep["id"], "dropped": drop["id"]}


def _when(event):
    at = event.get("at")
    if isinstance(at, (int, float)):
        return float(at)
    try:
        return float(str(at))
    except (TypeError, ValueError):
        return 0.0


def digest(cards, card_id, events, limit=12, preview=88):
    """what the human was doing by hand: the last things said, across every lane, in one order."""
    card = next((c for c in cards if c["id"] == card_id), None)
    if card is None:
        return {"card": None, "why": f"no card {card_id!r}"}
    handles = card.get("handles", {})
    mine = []
    for event in events:
        channel = event.get("channel", "")
        sender = event.get("sender", "")
        thread = event.get("thread", "")
        possibles = set(handles.get(channel, []))
        if channel in ("phone", "sms"):
            possibles |= set(handles.get("phone", [])) | set(handles.get("sms", []))
        try:
            hit = canonical(channel, sender) in possibles if channel in CHANNELS and sender else False
        except ValueError:
            hit = False
        if not hit and thread:
            try:
                hit = canonical(channel, thread) in possibles
            except ValueError:
                hit = False
        if hit:
            row = dict(event)
            row["preview"] = (event.get("body") or "")[:preview]
            mine.append(row)
    mine.sort(key=_when, reverse=True)
    recent = mine[:limit]
    return {"card": card["id"], "name": card["name"],
            "across": sorted({e.get("channel", "") for e in recent}),
            "count": len(mine), "recent": recent,
            "note": "one person, every carrier, one order: this is the paste somebody would have done by hand"}


SHELVES = {
    "owner": "humans/owner",
    "people": "humans/people",
    "agents": "agents",
}


def root(env=None):
    env = env if env is not None else os.environ
    where = env.get("COMMS_RECOGNICA_PATH") or env.get("COMMS_CARDS_PATH")
    if where:
        return pathlib.Path(where)
    return pathlib.Path.home() / ".local" / "share" / "comms" / "recognica"


def shelf(card):
    """which shelf a card sits on. agents are not people, and the owner is not just a contact."""
    if card.get("kind") == KIND_AGENT:
        return SHELVES["agents"]
    return SHELVES["owner"] if card.get("role") == ROLE_OWNER else SHELVES["people"]


def path(env=None):
    """kept for callers that expect one file: the old single-file store, if it exists."""
    where = root(env)
    if (where / "cards.json").is_file():
        return where / "cards.json"
    return where / SHELVES["people"] / "cards.json"


def load(env=None):
    """every shelf, or the old single file when that is all there is."""
    where = root(env)
    legacy = where / "cards.json"
    if legacy.is_file():
        try:
            return json.loads(legacy.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    cards = []
    for name in SHELVES.values():
        folder = where / name
        if not folder.is_dir():
            continue
        for item in sorted(folder.glob("*.json")):
            if item.name == "cards.json":
                continue
            try:
                card = json.loads(item.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(card, dict) and card.get("id"):
                cards.append(card)
    return cards


def save(cards, env=None):
    """write each card onto its own shelf, 0600, and drop files for cards that are gone.

    who talks to whom is personal: the shelf folders are readable only by their owner, and a card
    that moved between shelves does not leave a stale copy behind claiming the old role.
    """
    where = root(env)
    written = []
    keep = set()
    for card in cards:
        folder = where / shelf(card)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{card['id']}.json"
        target.write_text(json.dumps(card, indent=2, sort_keys=True))
        os.chmod(target, 0o600)
        keep.add(target)
        written.append(target)
    if where.is_dir():
        for folder in [where / name for name in SHELVES.values()]:
            if not folder.is_dir():
                continue
            for item in folder.glob("*.json"):
                if item not in keep:
                    item.unlink()
    return written[0] if len(written) == 1 else (written or where / SHELVES["people"])


def tree(cards):
    """what the book looks like: how many on each shelf, and which one is the owner."""
    owner = next((c for c in cards if c.get("role") == ROLE_OWNER and c.get("kind") != KIND_AGENT), None)
    humans = [c for c in cards if c.get("kind") != KIND_AGENT]
    agents = [c for c in cards if c.get("kind") == KIND_AGENT]
    people = [c for c in humans if c.get("role") != ROLE_OWNER]
    return {"root": "humans/{owner,people} and agents",
            "owner": ({"card": owner["id"], "name": owner["name"]} if owner else None),
            "counts": {"owner": 1 if owner else 0, "people": len(people), "agents": len(agents)},
            "shelves": {
                SHELVES["owner"]: [c["id"] for c in humans if c.get("role") == ROLE_OWNER],
                SHELVES["people"]: [c["id"] for c in people],
                SHELVES["agents"]: [c["id"] for c in agents],
            },
            "note": "the owner is a shelf, not a tag: a card is a contact until somebody says otherwise"}
