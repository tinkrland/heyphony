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
- **no attachments, no media.** this is text.

**two modes, and the difference is the carrier's, not ours.** a group chat has an id, and a reply into
that id is a group reply for everybody in it, which is what a carrier thread does. so a group here can
be either:

- **a carrier thread**, adopted from the id the carrier already uses (`adopt_thread`, `group adopt
  --thread`). the thread is the group. attribution is `by: "thread"` and certain, because the carrier
  named the conversation rather than us guessing from who is in it. what it needs is a send path that
  can address a thread, and each of the ten paths wired today says in `THREAD_SEND` why it cannot: they
  take one recipient per call. so a reply to a thread group is currently a fan-out, and the command
  output says so in `thread_gap` instead of letting anyone believe the group saw one message.

- **a fan-out**, which is this file's loop: each member gets a one-to-one text from the did, with no
  sign that anyone else exists. that is a property of a single-recipient send path and not of sms, which
  is the correction worth keeping: the earlier version of this page claimed most carriers cannot carry a
  group text, and that was wrong about the carriers and only right about our own rail. the shared
  transcript lives in *your* records and not in their phones, and the readme and the command output both
  say which mode is in force, since a person who thinks they are in a group chat and is not will answer
  as if they were.
"""
import hashlib
import json
import os
import pathlib
import time

MAX_MEMBERS = 4

# the alphabet a code is drawn from: no B, I, O, S, 0, 1, 2, 5 or 8, because a code gets read out
# loud, copied off a screen and typed back, and those are the pairs that turn one into another
CODE_ALPHABET = "ACDEFGHJKLMNPQRTUVWXY34679"
CODE_LENGTH = 4
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


def create(name, with_, store=None, number=None):
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
             "members": members, "created": int(time.time()), "messages": [],
             "code": new_code(name, members, data["groups"]),
             # a group can hold a did of its own, in which case a reply arrives addressed to it and
             # needs no code and no guess. optional, because it costs a number per group
             "number": (str(number).strip() or None) if number else None}
    group = {k: v for k, v in group.items() if v is not None or k in ("members", "messages")}
    data["groups"].append(group)
    save(data, store)
    return {"ok": True, "group": group, "code": group["code"], "tag": tag_for(group),
            "what_members_see": WHAT_MEMBERS_SEE, "the_code_is_not_a_secret": CODE_IS_NOT_A_SECRET}


CODE_IS_NOT_A_SECRET = ("the code is not a secret: it names a conversation, not a person. it rides on "
                        "the message and anybody who reads it can quote it, so it is never a way to "
                        "prove who is writing, only which group they mean")


def new_code(name, members, groups):
    """four characters drawn from the group itself, and never one a live group already answers to."""
    held = {g.get("code") for g in groups if g.get("code")}
    seed = f"{name}|{'|'.join(sorted(m['number'] for m in members))}"
    for salt in range(0, 500):
        digest = hashlib.sha256(f"{seed}|{salt}".encode()).digest()
        code = "".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in digest[:CODE_LENGTH])
        if code not in held:
            return code
    return "".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in digest[-CODE_LENGTH:])


def tag_for(group):
    """what a member sees on the end of the message: short enough to be eight characters and no more."""
    return f"ref {group['code']}"


def tag_text(text, group):
    return f"{text}{TAG_JOINER}{tag_for(group)}"


TAG_JOINER = "\n\n"


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


def attribute(groups, number):
    """which named groups a number belongs to, from our own records rather than the carrier.

    a member's reply arrives as an ordinary one-to-one text with no group marker on it: the carrier
    carries no group thread, because we never started one. so membership is the only join available,
    it is ours, and a person in two groups gets both rather than a silently picked one.
    """
    target = _digits(number)
    hits = []
    for group in groups or []:
        for member in group.get("members", []):
            if _digits(member.get("number")) == target:
                hits.append({"id": group["id"], "name": group["name"],
                             "member": member.get("name")})
                break
    return hits


def _digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def thread(group_id, store=None, messages=None):
    """my sends and their replies in one order, because that is the conversation a person had.

    the carrier contributes nothing here: the sends come from this store and the replies are matched
    by membership, so an inbound row is a member's own text rather than a group message.
    """
    group = find(load(store)["groups"], group_id)
    if not group:
        return {"ok": False, "why": "no such group"}
    rows = []
    for entry in group.get("messages", []):
        rows.append({"at": entry.get("at"), "direction": "out", "who": "you",
                     "text": entry.get("text"), "tag": entry.get("tag"),
                     "sent": entry.get("sent"), "of": entry.get("of")})
    members = {_digits(m["number"]): m["name"] for m in group.get("members", [])}
    for entry in (messages if messages is not None else _inbox()):
        sender = _digits(entry.get("sender"))
        if sender in members:
            rows.append({"at": entry.get("at"), "direction": "in", "who": members[sender],
                         "text": entry.get("body"), "from": entry.get("sender"),
                         "id": entry.get("id")})
    rows.sort(key=lambda row: float(row.get("at") or 0))
    return {"ok": True, "group": {"id": group["id"], "name": group["name"]},
            "rows": rows, "count": len(rows), "what_members_see": WHAT_MEMBERS_SEE,
            "means": ("an in row is a member's own text to your did, matched by membership rather "
                      "than by a group marker, because no group thread exists to carry one")}


def _inbox():
    try:
        from src.manage import inbox as store
        return store.read()
    except Exception:
        return []


def code_of(text):
    """the code a body quotes, if it quotes one. explicit rather than a bare token, because a
    four character string that happens to fall in the alphabet is a coincidence, not an address."""
    import re
    found = re.search(r"\bref\s+([A-Za-z0-9]{4})\b", str(text or ""))
    if found:
        return found.group(1).upper()
    bare = str(text or "").strip().upper()
    return bare if len(bare) == CODE_LENGTH and all(ch in CODE_ALPHABET for ch in bare) else None


def attribute_inbound(groups=None, sender=None, text=None, recipient=None, thread=None):
    """which group an inbound text belongs to, and on what evidence.

    the ladder is code, then the group's own number, then membership. only the first two are evidence:
    a quoted code or an addressed number says which conversation this is, while membership says only
    that this person is in one, which is a guess from our own records and is reported as one.
    """
    groups = load()["groups"] if groups is None else groups
    if thread:
        hit = next((g for g in groups if g.get("thread") and str(g["thread"]) == str(thread)), None)
        if hit:
            member = next((m.get("name") for m in hit.get("members", [])
                           if _digits(m.get("number")) == _digits(sender)), None)
            return {"groups": [{"id": hit["id"], "name": hit["name"], "member": member}],
                    "by": "thread", "certain": True, "thread": str(thread)}
    code = code_of(text)
    if code:
        hit = next((g for g in groups if g.get("code") == code), None)
        if hit:
            member = next((m.get("name") for m in hit.get("members", [])
                           if _digits(m.get("number")) == _digits(sender)), None)
            return {"groups": [{"id": hit["id"], "name": hit["name"], "member": member}],
                    "by": "code", "certain": True, "code": code}
    if recipient:
        hit = next((g for g in groups if g.get("number")
                    and _digits(g["number"]) == _digits(recipient)), None)
        if hit:
            member = next((m.get("name") for m in hit.get("members", [])
                           if _digits(m.get("number")) == _digits(sender)), None)
            return {"groups": [{"id": hit["id"], "name": hit["name"], "member": member}],
                    "by": "number", "certain": True}
    hits = attribute(groups, sender)
    if not hits:
        return {"groups": [], "by": None, "certain": False}
    return {"groups": hits, "by": "membership" if len(hits) == 1 else "ambiguous",
            "certain": False}


ATTRIBUTION_MEANS = {
    "thread": "the carrier put this text in a thread it named, so the conversation is the thread's "
              "rather than a guess from who is in it",
    "code": "the body quotes this group's code, so the conversation is named rather than guessed",
    "number": "the text arrived on this group's own number, so it is addressed rather than guessed",
    "membership": "no code in the body, so the group comes from our own membership records and is a "
                  "guess rather than a fact",
    "ambiguous": "the sender is in more than one group and the body names none of them, so every "
                 "candidate is reported and none is picked",
}


def adopt_thread(thread, participants=None, name=None, store=None):
    """a group that exists because a carrier said so.

    the owner's correction, encoded: a group chat has an id, a reply into that id is a group reply
    for everybody in it, and our records should follow the carrier rather than decide for themselves
    that no group exists. participants are named by number when the carrier gives no names, which is
    honest: a carrier knows numbers, we know names, and the name can be filled in later.
    """
    if not thread:
        return {"ok": False, "why": "a thread needs the carrier's own id, not a name we made up"}
    data = load(store)
    live = next((g for g in data["groups"] if g.get("thread") == str(thread)), None)
    if live:
        return {"ok": True, "group": live, "adopted": False,
                "why": "this thread is already a group here, so nothing was duplicated"}
    members = []
    for entry in participants or []:
        if isinstance(entry, dict):
            number = str(entry.get("number") or "").strip()
            label = str(entry.get("name") or number).strip()
        else:
            raw = str(entry).strip()
            label, _, number = raw.partition("=")
            if not number:
                label, number = raw, raw
            label, number = label.strip(), number.strip()
        if number and not any(_digits(m["number"]) == _digits(number) for m in members):
            members.append({"name": label or number, "number": number})
    if len(members) < 2:
        return {"ok": False, "participants": len(members),
                "why": "a thread with one participant is a thread, not a group",
                "from_carrier": "the carrier named the thread but not its people, so there is "
                                "nothing to reply to that would be a group reply"}
    group = {"id": new_id(name or f"thread {thread}", [m["number"] for m in members]),
             "name": (name or f"thread {thread}").strip(), "members": members,
             "created": int(time.time()), "messages": [], "thread": str(thread),
             "code": new_code(name or str(thread), members, data["groups"]),
             "adopted_from": "carrier"}
    data["groups"].append(group)
    save(data, store)
    return {"ok": True, "group": group, "adopted": True, "thread": str(thread),
            "means": ("this group is the carrier's thread, so a reply sent into the thread is a "
                      "group reply for everybody in it"),
            "what_members_see": WHAT_MEMBERS_SEE_CARRIER}


WHAT_MEMBERS_SEE_CARRIER = ("a carrier thread carries the message to every member, so they see it "
                            "in the group chat they are already in. that needs a send path that "
                            "addresses the thread, which the ten paths wired here do not")


def listing(store=None):
    groups = load(store)["groups"]
    return {"count": len(groups),
            "groups": [{"id": g["id"], "name": g["name"], "members": len(g["members"]),
                        "messages": len(g.get("messages", []))} for g in groups],
            "max_members": MAX_MEMBERS, "what_members_see": WHAT_MEMBERS_SEE}


def reply(group_id, text, provider, from_number, allow=False, store=None, opener=None,
          replying=None, tag=True):
    """answer a member in the group rather than only to them.

    the replier has a one-to-one thread with your did and nothing else, so sending to every member
    is what "reply to the group" can mean: the replier gets it in the same thread they used, and
    everyone else gets it as their own one-to-one. nobody sees a group, and the output says so.
    """
    answer = say(group_id, text, provider=provider, from_number=from_number, allow=allow,
                 store=store, opener=opener, tag=tag)
    # the shape of a group reply does not depend on whether this one left the machine, so a draft
    # carries the same explanation as a sent message
    answer["reply"] = True
    answer["replying_to"] = replying
    answer["means"] = ("the replier gets this in the same one-to-one thread they used, and every "
                       "other member gets their own copy, because no group thread exists for one "
                       "message to arrive in")
    return answer


def say(group_id, text, provider, from_number, allow=False, store=None, opener=None, tag=True):
    """one message, one member at a time, through the rail that already refuses lists."""
    from src.manage.outgoing import send as outbox
    group = find(load(store)["groups"], group_id)
    if not group:
        return {"ok": False, "why": "no such group", "sent": 0}
    sent_text = tag_text(text, group) if tag and group.get("code") else text
    results = []
    for member in group["members"]:
        answer = outbox.send(provider=provider, from_number=from_number, to=member["number"],
                             text=sent_text, allow=allow, opener=opener)
        results.append({"name": member["name"], "to": member["number"], "sent": bool(answer.get("sent")),
                        "why": answer.get("why")})
    sent = sum(1 for row in results if row["sent"])
    delivered_as, thread_gap = "fanout", None
    if group.get("thread"):
        # the owner's correction, turned into an honest field: a reply into a carrier thread is a
        # group reply for everyone, and a fan-out of one-to-one texts is not, so say which happened
        cap = outbox.thread_send(provider)
        delivered_as = "thread" if cap["ok"] else "fanout"
        thread_gap = (None if cap["ok"] else
                      f"this group is a carrier thread, and {provider} cannot address a thread: "
                      f"{cap['why']}. so each member gets their own one-to-one text instead, which "
                      f"will not appear in the group chat the others are reading")
    data = load(store)
    live = find(data["groups"], group["id"])
    if live is not None:
        live.setdefault("messages", []).append({"at": int(time.time()), "text": text,
                                                "sent_text": sent_text,
                                                "delivered_as": delivered_as,
            "thread": group.get("thread"),
            "thread_gap": thread_gap,
            "tag": tag_for(group) if sent_text != text else None,
                                                "sent": sent, "of": len(results)})
        save(data, store)
    return {"ok": sent == len(results) and sent > 0, "sent": sent, "of": len(results),
            "results": results,
            "draft": not allow,
            "why": ("draft: pass --send and set HEYPHONY_SEND=allowed to send" if not allow else
                    f"{sent} of {len(results)} members accepted the message"),
            "delivered_as": delivered_as,
            "thread": group.get("thread"),
            "thread_gap": thread_gap,
            "tag": tag_for(group) if sent_text != text else None,
            "code": group.get("code"),
            "the_code_is_not_a_secret": CODE_IS_NOT_A_SECRET,
            "segments": ("the tag is 8 characters, so a body near the segment ceiling can become a "
                         "second segment where one was drafted. --no-tag sends the body alone"),
            "what_members_see": WHAT_MEMBERS_SEE}
