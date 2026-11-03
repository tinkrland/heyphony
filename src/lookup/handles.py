"""handles: what a username can say, which is mostly where a number is not needed.

a username matters to this tool for one reason: on signal and on whatsapp it is enough to start a chat
without either side giving up a phone number. that makes it the one address form this package cannot
route, and the lookup should say so plainly rather than imply a number is hiding behind it.

what it will not do is check whether an account exists. every way to find that out is a message to a
stranger, and a tool that pings people to satisfy a curiosity is a nuisance with a cli.
"""
import json
import pathlib
import re

DATA = pathlib.Path(__file__).with_name("usernames.json")
_DATA = None

SIGNAL_SHAPE = re.compile(r"^(?P<nick>[a-z0-9_]+)\.(?P<digits>\d{2,})$")
# what somebody types when they mean a signal username, before the rules get a say
SIGNAL_INTENT = re.compile(r"^[a-z0-9_]+\.[0-9]+$")
HANDLE_SHAPE = re.compile(r"^[a-z0-9._]+$")

NOTES = {
    "no_network": "no request leaves the machine. existence and reachability are withheld because "
                  "every probe would be a message to somebody who did not ask",
    "handle_not_identity": "a username is a handle rather than an identity: people change them, and "
                           "signal keeps a hash rather than the name",
}


def platforms():
    global _DATA
    if _DATA is None:
        _DATA = json.loads(DATA.read_text())
    return _DATA


def normalise(value):
    """what a platform would store: lowercase, and the @ people type is not part of the name."""
    got = str(value or "").strip()
    typed_at = got.startswith("@")
    return got.lstrip("@").strip().lower(), typed_at


def _outside(data, name, value):
    """report a bound the value breaks without calling a person's handle invalid over it."""
    out = []
    if name == "signal":
        nick = value.split(".", 1)[0]
        if len(nick) < data["nickname_min"] or len(nick) > data["nickname_max"]:
            out.append(f"nickname is {len(nick)} characters, and the carried rule says "
                       f"{data['nickname_min']} to {data['nickname_max']}")
        if not re.match(r"^[a-z0-9_]+$", nick):
            out.append(f"nickname `{nick}` is outside the carried set ({data['nickname_charset']})")
    else:
        if len(value) > data["handle_max"]:
            out.append(f"handle is {len(value)} characters, and the carried rule says at most "
                       f"{data['handle_max']}")
        if not HANDLE_SHAPE.match(value):
            out.append(f"handle is outside the carried set ({data['handle_charset']})")
    return out


def _shape(name, data, value):
    """the part that is fatal: whatsapp needs no discriminator, signal needs one."""
    if not value:
        return False, "empty"
    if name == "signal":
        found = SIGNAL_SHAPE.match(value)
        if not found:
            if "." not in value:
                return False, ("a signal username carries a numeric discriminator, so a bare nickname "
                               "is not one: signal adds the number itself when you share a username")
            return False, ("a signal username ends in a dot and at least "
                           f"{data['discriminator_digits_min']} digits, and this does not")
        return True, f"a nickname and a {len(found.group('digits'))} digit discriminator"
    if not HANDLE_SHAPE.match(value):
        return False, f"not a handle in the carried set ({data['handle_charset']})"
    return True, "a handle with no discriminator, which is whatsapp's shape and not signal's"


def guess(value):
    """which platform the string could belong to, and whether that is a fact or a reading."""
    got, _ = normalise(value)
    if SIGNAL_SHAPE.match(got) or SIGNAL_INTENT.match(got):
        return "signal", False, ("the shape is signal's, and it is also a legal whatsapp handle, so the "
                                 "string alone does not settle which account it names")
    if HANDLE_SHAPE.match(got):
        return "whatsapp", False, ("a bare handle is whatsapp's shape, and also every other platform's, "
                                  "so the shape is a reading and not a fact")
    return None, False, "the string is a handle on neither platform carried here"


def lookup(value, platform=None):
    """what the handle says, what it cannot say, and nothing beyond that."""
    data = platforms()
    table = data["platforms"]
    raw = str(value or "").strip()
    got, typed_at = normalise(raw)
    chosen, certain, guessed_why = (platform, True, "the platform was named") if platform in table \
        else guess(raw)
    answer = {"input": raw, "kind": "username", "normalised": got, "typed_at": typed_at,
              "platform": chosen, "platform_certain": certain, "verified": False,
              "notes": NOTES, "contactable_without_number": bool(chosen),
              "number_known": False,
              "privacy": {"derived_from": "the string, read locally",
                          "network": "no request leaves the machine",
                          "retention": "nothing is stored"}}
    if not chosen:
        answer.update({"valid": False, "shape": None, "evidence": [],
                       "withheld": {"everything": guessed_why},
                       "why": f"not a username on either platform carried here: {guessed_why}"})
        return answer

    entry = table[chosen]
    ok, shape_why = _shape(chosen, entry, got)
    answer.update({"valid": ok, "shape": shape_why, "display": entry["display"]})
    if not certain:
        answer["why"] = guessed_why
    answer["withheld"] = {
        "exists": "whether an account answers to this handle needs a message to it, and this is a "
                  "lookup. a probe here would be contact",
        "identity": NOTES["handle_not_identity"],
        "phone_number": "a username exists so the number stays private. nothing in the string carries "
                        "one, and asking for it is exactly the thing the username avoids",
    }
    if chosen == "whatsapp":
        answer["withheld"]["chat"] = entry["key"]
    if chosen == "signal":
        answer["withheld"]["stability"] = ("signal keeps a hash of the username rather than the "
                                           "username, and usernames are built to be changed and "
                                           "revoked, so the same string next month may be somebody "
                                           "else")
    answer["evidence"] = [
        {"strength": "shape", "source": f"{entry['display']}'s published username form, carried in "
                                        f"usernames.json", "why": entry["shape"]},
        {"strength": "unseeded", "source": "no probe is wired",
         "why": "existence, identity and reachability all need a message, so all three are withheld"},
    ]
    if not ok:
        answer["why"] = shape_why
    also = []
    for name in [n for n in table if n != chosen]:
        theirs_ok, theirs_why = _shape(name, table[name], got)
        if theirs_ok:
            also.append({"platform": name, "valid": True, "shape": theirs_why,
                         "note": "the same string is a legal name on both platforms and names a "
                                 "different account on each, so the reading has to be chosen rather "
                                 "than assumed"})
    if also:
        answer["also_read_as"] = also
    outside = _outside(entry, chosen, got) if ok else []
    if outside:
        answer["outside_shape"] = outside
    answer["probes"] = [{"name": "send-and-see", "would_answer": "whether the handle resolves",
                         "wired": False,
                         "refused": "it messages a stranger to satisfy a lookup, so it is not offered"}]
    return answer
