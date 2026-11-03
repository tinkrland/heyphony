"""groups: a conversation with two or three named people, which is not a list.

the outbound rail refuses a list on purpose, and that refusal is about **broadcast**: one text to many
strangers, at machine pace, with no conversation on the other end. a group chat is the other thing. it
is small, the people are named, each of them knows the others, and everybody is in it on purpose.

so this file does the loop that the rail refuses, under conditions narrow enough that the difference is
structural rather than a promise:

- **four members, hard ceiling.** past that it is not a conversation, it is an audience. the ceiling is
  a constant, not a flag.
- **every member is a person with a name.** "with": [{"name": ..., "number": "+1..."}] and both are
  required. an unnamed number is refused, because the name is what makes it a named group rather than a
  paste of numbers.
- **every message goes through the same rail, one recipient at a time.** each send carries its own
  gate, its own 1600 character ceiling and its own provider path, so a group is not a way around any of
  them. one member failing does not silently become "sent to the group".
- **no attachments, no mms, no media.** this is text. a real group mms is a carrier product on some
  north american plans and it is not wired here.

**what a member sees, said plainly, because it is the one thing people assume wrong.** most carriers do
not carry a group sms as a group. each member gets a one-to-one text from the did, with no sign that
anyone else exists. so this is a transcript that is shared in *your* records and not in their phones.
the readme and the command output both say so, since a person who thinks they are in a group chat and
is not will answer as if they were.
"""
import hashlib
import json
import os
import pathlib
import time

MAX_MEMBERS = 4
STORE = pathlib.Path(os.environ.get("HEYPHONY_GROUPS")
                     or pathlib.Path.home() / ".local/share/telephony/groups.json")


def path():
    return pathlib.Path(os.environ.get("HEYPHONY_GROUPS")
                        or pathlib.Path.home() / ".local/share/telephony/groups.json")


def _slug(name):
    clean = "".join(ch if ch.isalnum() else "-" for ch in str(name or "").lower()).strip("-")
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean or "group"


def new_id(name, members):
    seed = _slug(name) + "|" + "|".join(sorted(str(m) for m in members)) + "|" + str(int(time.time()))
    return _slug(name)[:24] + "-" + hashlib.sha256(seed.encode()).hexdigest()[:6]


def load(store=None):
    target = pathlib.Path(store) if store else path()
    if not target.exists():
        return {"groups": []}
    try:
        return json.loads(target.read_text())
    except ValueError:
        return {"groups": []}


def save(data, store=None):
    target = pathlib.Path(store) if store else path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.chmod(target, 0o600)
    return target


def _clean_members(with_):
    """a member is a name and a number. anything else is refused with the reason, not coerced."""
    members, problems, seen = [], [], set()
    for item in with_ or []:
        if not isinstance(item, dict):
            problems.append({"why": "a member is {name, number}, not a bare number", "got": item})
            continue
        name = str(item.get("name") or "").strip()
        number = str(item.get("number") or "").strip()
        if not name:
            problems.append({"why": "a member needs a name", "number": number})
        if not number.startswith("+") or len(number) < 8:
            problems.append({"why": "a member's number must be e164", "got": number})
        if number in seen:
            problems.append({"why": "the same number twice", "number": number})
        seen.add(number)
        members.append({"name": name, "number": number})
    return members, problems


def create(name, with_, store=None):
    """a named conversation, small enough to be one."""
    members, problems = _clean_members(with_)
    if not str(name or "").strip():
        problems.append({"why": "a group needs a name, because the name is how it is referred to"})
    if len(members) < 2:
        problems.append({"why": "two members is a group, one member is a thread",
                         "members": len(members)})
    if len(members) > MAX_MEMBERS:
        problems.append({"why": "past four it is an audience, not a conversation",
                         "members": len(members), "max": MAX_MEMBERS})
    if problems:
        return {"ok": False, "problems": problems,
                "why": "refused: a group is small and named, and the problems above say why"}
    data = load(store)
    group = {"id": new_id(name, [m["number"] for m in members]), "name": str(name).strip(),
             "members": members, "created": int(time.time()), "messages": []}
    data["groups"].append(group)
    save(data, store)
    return {"ok": True, "group": group, "what_members_see": WHAT_MEMBERS_SEE}


WHAT_MEMBERS_SEE = ("each member gets a one-to-one text from your did. no carrier group thread is "
                    "started, so they do not see each other's numbers and cannot text the group.")


def find(groups, group_id):
    for group in groups:
        if group["id"] == group_id or group["name"].lower() == str(group_id).lower():
            return group
    return None


def show(group_id, store=None):
    group = find(load(store)["groups"], group_id)
    if not group:
        return {"ok": False, "why": "no such group", "groups": [g["id"] for g in load(store)["groups"]]}
    return {"ok": True, "group": group, "what_members_see": WHAT_MEMBERS_SEE}


def listing(store=None):
    groups = load(store)["groups"]
    return {"count": len(groups),
            "groups": [{"id": g["id"], "name": g["name"], "members": len(g["members"]),
                        "messages": len(g.get("messages", []))} for g in groups],
            "max_members": MAX_MEMBERS, "what_members_see": WHAT_MEMBERS_SEE}


def say(group_id, text, provider, from_number, allow=False, store=None, opener=None):
    """one message, one member at a time, through the rail that already refuses lists."""
    from src.manage.outgoing import send as outbox
    group = find(load(store)["groups"], group_id)
    if not group:
        return {"ok": False, "why": "no such group", "sent": 0}
    results = []
    for member in group["members"]:
        answer = outbox.send(provider=provider, from_number=from_number, to=member["number"],
                             text=text, allow=allow, opener=opener)
        results.append({"name": member["name"], "to": member["number"], "sent": bool(answer.get("sent")),
                        "why": answer.get("why")})
    sent = sum(1 for row in results if row["sent"])
    data = load(store)
    live = find(data["groups"], group["id"])
    if live is not None:
        live.setdefault("messages", []).append({"at": int(time.time()), "text": text,
                                                "sent": sent, "of": len(results)})
        save(data, store)
    return {"ok": sent == len(results) and sent > 0, "sent": sent, "of": len(results),
            "results": results,
            "draft": not allow,
            "why": ("draft: pass --send and set HEYPHONY_SEND=allowed to send" if not allow else
                    f"{sent} of {len(results)} members accepted the message"),
            "what_members_see": WHAT_MEMBERS_SEE}
