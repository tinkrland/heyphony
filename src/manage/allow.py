"""allow: who the agent is willing to hear from, decided before a message is written down.

a number that texts the agent is a stranger until this file says otherwise, and the cheapest place to
say so is the door: the catcher normalizes a message, asks `decide`, and stores it or does not. nothing
downstream has to remember to filter, because nothing downstream ever sees the refused one.

one policy, one mode, and toggles that stack on top of it:

    mode      who gets in
    ------    ------------------------------------------------------------------------------
    open      everybody. the default is NOT this. an unset policy is `list`, see below.
    list      only numbers on the allowlist. an empty list admits nobody, which is the point.
    local     numbers whose country dial code matches the home country.
    regions   countries on `allow_countries`, minus countries on `block_countries`.

    toggles   `also_allow_list`  a listed number gets in whatever the mode says (on by default)
              `block_wins`       a blocked country or number is refused even if it is listed

the default is closed on purpose. an agent that answers anyone is an agent that can be talked into
things by anyone, and a policy that has to be switched ON to protect you is a policy that is off the
first time a webhook arrives. unset means `list` with an empty list, so nothing is admitted until a human
adds a number.

country detection reads the e164 prefix and nothing else. dial codes are prefix free, so the longest
match is the answer, with one honest exception: +1 is shared by the united states, canada and a run of
caribbean nations, and the number alone cannot tell them apart without the area code table. so `+1` is
treated as the north american numbering plan region `NANP`, and `local` for a +1 home accepts all of it.
saying "us only" and meaning it needs the area code table, and a guess would be a quiet hole.
"""
import json
import os
import re
from pathlib import Path

MODES = ("open", "list", "local", "regions")
DEFAULT_MODE = "list"

E164 = re.compile(r"\+[1-9][0-9]{6,14}")

# dial codes the repo already talks about, plus the common ones. longest prefix wins, so +370 is
# lithuania and not +3, and +1 is the whole shared plan. an unlisted code is "unknown", which no region
# rule admits: a number we cannot place is not a number we can vouch for.
DIAL_CODES = {
    "+1": "NANP", "+7": "RU", "+20": "EG", "+27": "ZA", "+30": "GR", "+31": "NL", "+32": "BE",
    "+33": "FR", "+34": "ES", "+36": "HU", "+39": "IT", "+40": "RO", "+41": "CH", "+43": "AT",
    "+44": "GB", "+45": "DK", "+46": "SE", "+47": "NO", "+48": "PL", "+49": "DE", "+51": "PE",
    "+52": "MX", "+53": "CU", "+54": "AR", "+55": "BR", "+56": "CL", "+57": "CO", "+58": "VE",
    "+60": "MY", "+61": "AU", "+62": "ID", "+63": "PH", "+64": "NZ", "+65": "SG", "+66": "TH",
    "+81": "JP", "+82": "KR", "+84": "VN", "+86": "CN", "+90": "TR", "+91": "IN", "+92": "PK",
    "+93": "AF", "+94": "LK", "+95": "MM", "+98": "IR", "+212": "MA", "+213": "DZ", "+216": "TN",
    "+234": "NG", "+254": "KE", "+351": "PT", "+352": "LU", "+353": "IE", "+354": "IS",
    "+358": "FI", "+359": "BG", "+370": "LT", "+371": "LV", "+372": "EE", "+380": "UA",
    "+381": "RS", "+385": "HR", "+386": "SI", "+420": "CZ", "+421": "SK", "+852": "HK",
    "+886": "TW", "+971": "AE", "+972": "IL", "+966": "SA",
}

# the codes that name a country, longest first, so the loop below is a plain first match
_CODES = sorted(DIAL_CODES, key=len, reverse=True)

# a country is also a name people type. both forms are accepted and both are stored as the code
NAMES = {
    "united states": "NANP", "usa": "NANP", "canada": "NANP", "us": "NANP", "nanp": "NANP",
    "united kingdom": "GB", "uk": "GB", "britain": "GB", "gb": "GB",
    "australia": "AU", "au": "AU", "sweden": "SE", "se": "SE", "lithuania": "LT", "lt": "LT",
    "poland": "PL", "pl": "PL", "netherlands": "NL", "nl": "NL", "india": "IN", "in": "IN",
    "germany": "DE", "de": "DE", "france": "FR", "fr": "FR", "ireland": "IE", "ie": "IE",
    "new zealand": "NZ", "nz": "NZ", "singapore": "SG", "sg": "SG", "japan": "JP", "jp": "JP",
}

REFUSED = {
    "open-by-default": "an unset policy admits nobody, so protection does not depend on being switched on",
    "guess-a-country": "a number the prefix table cannot place is refused by every region rule",
    "us-only-from-a-plus-one": ("+1 is one numbering plan shared by several countries, and this file will "
                                "not pretend the digits say which"),
    "silent-edit": "every change to the policy says what it changed, so a widened door is never a surprise",
    "list-in-the-message": "a sender cannot add itself: only the owner's command edits the list",
    "name-as-a-number": ("an alphanumeric sender id (AMAZON, a short code) has no country, so only open mode "
                        "admits it and every other mode refuses it under its own name"),
    "spoofed-local": ("the sender is the number the carrier reports, which a provider vouches for and this "
                      "file does not verify any further than that"),
}


def policy_path(path=None):
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return Path(path or os.environ.get("HEYPHONY_ALLOW") or base / "heyphony" / "allow.json")


def default_policy():
    return {"mode": DEFAULT_MODE, "home": None, "allow_numbers": [], "block_numbers": [],
            "allow_countries": [], "block_countries": [], "also_allow_list": True, "block_wins": True}


def normalize_number(raw):
    """a plus and digits, or None. spaces, dashes, dots and brackets are removed first.

    two shapes beyond a clean e164 are accepted because providers really send them: a leading 00 in
    place of the plus, and bare digits that already begin with a known dial code (some carriers drop the
    plus). bare digits are only believed when the front of them is a code this file can place, so a
    random run of digits is still not a number. a unicode digit is not a digit here: `str.isdigit` would
    say yes to a fullwidth four, and a sender that only looks like a number is the one to distrust.
    """
    if raw is None or isinstance(raw, (list, tuple, dict, bytes)):
        return None
    text = re.sub(r"[\s().\-]", "", str(raw))
    if text.startswith("00"):
        text = "+" + text[2:]
    if text and not text.startswith("+") and text.isascii() and text.isdigit() and len(text) >= 7:
        if any(("+" + text).startswith(code) for code in _CODES):
            text = "+" + text
    return text if E164.fullmatch(text) else None


def is_name(raw):
    """an alphanumeric sender id like AMAZON or a short code: letters, digits, no plus, not a number."""
    if raw is None or isinstance(raw, (list, tuple, dict, bytes)):
        return False
    text = str(raw).strip()
    if not text or normalize_number(text) is not None:
        return False
    # the gsm alphanumeric sender id is at most eleven characters, and a short code is digits only. no
    # internal spaces: "not a number" is a sentence, and a sentence is not a sender
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._&-]{0,10}", text))


def country_of(number):
    """the region for an e164 number, or None. the longest dial code that matches wins."""
    number = normalize_number(number)
    if number is None:
        return None
    for code in _CODES:
        if number.startswith(code):
            return DIAL_CODES[code]
    return None


def region(name):
    """a country name or code in, the stored region code out. unknown names are refused, not guessed."""
    key = str(name or "").strip().lower()
    if key in NAMES:
        return NAMES[key]
    upper = key.upper()
    if upper in set(DIAL_CODES.values()):
        return upper
    if key.startswith("+") and key in DIAL_CODES:
        return DIAL_CODES[key]
    return None


def load(path=None):
    target = policy_path(path)
    if not target.exists():
        return default_policy()
    try:
        data = json.loads(target.read_text())
    except ValueError:
        # a broken policy file must close the door, not open it
        broken = default_policy()
        broken["broken"] = True
        return broken
    merged = default_policy()
    merged.update({k: v for k, v in data.items() if k in merged})
    if merged["mode"] not in MODES:
        merged["mode"] = DEFAULT_MODE
    return merged


def save(policy, path=None):
    target = policy_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: policy[k] for k in default_policy()}
    target.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")
    os.chmod(target, 0o600)
    return target


def decide(sender, policy=None, path=None):
    """(allowed, why). the one question the catcher asks, answered the same way every time."""
    policy = policy or load(path)
    number = normalize_number(sender)
    if number is None:
        # a brand name or short code has no country to check. only `open` admits it, because a list of
        # e164 numbers and a set of countries cannot vouch for a name, and saying "no-number" for it
        # would send the owner looking for a bug in their number format
        if is_name(sender):
            if policy["mode"] == "open" and str(sender).strip().upper() not in {
                    str(n).strip().upper() for n in policy.get("block_numbers", [])}:
                return True, "open-name"
            return False, "alphanumeric-sender"
        return False, "no-number"
    place = country_of(number)

    if number in policy["block_numbers"]:
        return False, "number-blocked"
    if place and place in policy["block_countries"] and policy["block_wins"]:
        return False, "country-blocked"

    listed = number in policy["allow_numbers"]
    if listed and policy["also_allow_list"]:
        return True, "on-the-list"

    mode = policy["mode"]
    if mode == "open":
        return True, "open"
    if mode == "list":
        return False, "not-on-the-list"
    if mode == "local":
        home = policy.get("home")
        if not home:
            return False, "no-home-country"
        if place is None:
            return False, "country-unknown"
        return (True, "local") if place == home else (False, "not-local")
    if mode == "regions":
        if place is None:
            return False, "country-unknown"
        if place in policy["block_countries"]:
            return False, "country-blocked"
        if policy["allow_countries"]:
            return (True, "country-allowed") if place in policy["allow_countries"] else (False, "country-not-allowed")
        return False, "no-countries-allowed"
    return False, "unknown-mode"


def refusals_path(path=None):
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return Path(path or base / "heyphony" / "refused.jsonl")


def record_refusal(sender, why, path=None, at=None):
    """one line per refused message: when, why, which region. never the body, never the whole number.

    a door that refuses in silence looks identical to a webhook that is broken, so the refusals are
    countable. the number is cut to its dial code and last two digits, enough to tell two senders apart
    and not enough to rebuild a contact list from a log.
    """
    import time

    number = normalize_number(sender) or str(sender or "")
    short = number[:4] + "..." + number[-2:] if len(number) > 8 else number
    target = refusals_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a") as handle:
        handle.write(json.dumps({"at": int(at or time.time()), "why": why,
                                 "region": country_of(number), "sender": short}, sort_keys=True) + "\n")
    os.chmod(target, 0o600)
    return target


def refusal_summary(path=None):
    """how many were turned away and why, so a policy that is too tight is visible."""
    target = refusals_path(path)
    if not target.exists():
        return {"refused": 0, "by_reason": {}, "by_region": {}}
    reasons, regions, total = {}, {}, 0
    for line in target.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        total += 1
        reasons[row.get("why")] = reasons.get(row.get("why"), 0) + 1
        regions[row.get("region") or "unknown"] = regions.get(row.get("region") or "unknown", 0) + 1
    return {"refused": total, "by_reason": reasons, "by_region": regions}


def _add(items, value):
    return items if value in items else items + [value]


def _drop(items, value):
    return [i for i in items if i != value]


def apply(policy, action, value=None):
    """one edit in, (new policy, what changed) out. nothing is saved here."""
    policy = json.loads(json.dumps(policy))
    if action == "mode":
        if value not in MODES:
            return policy, {"ok": False, "why": f"mode must be one of {list(MODES)}"}
        before, policy["mode"] = policy["mode"], value
        return policy, {"ok": True, "changed": f"mode {before} -> {value}"}
    if action == "home":
        code = region(value)
        if not code:
            return policy, {"ok": False, "why": f"no such country: {value}"}
        policy["home"] = code
        return policy, {"ok": True, "changed": f"home -> {code}"}
    if action in ("allow", "unallow", "block", "unblock"):
        number = normalize_number(value)
        if number is None:
            return policy, {"ok": False, "why": "a number in e164 form, with a plus and digits"}
        key = "allow_numbers" if action in ("allow", "unallow") else "block_numbers"
        policy[key] = (_add if action in ("allow", "block") else _drop)(policy[key], number)
        return policy, {"ok": True, "changed": f"{action} {number}"}
    if action in ("allow-country", "unallow-country", "block-country", "unblock-country"):
        code = region(value)
        if not code:
            return policy, {"ok": False, "why": f"no such country: {value}"}
        key = "allow_countries" if action in ("allow-country", "unallow-country") else "block_countries"
        policy[key] = (_add if action in ("allow-country", "block-country") else _drop)(policy[key], code)
        return policy, {"ok": True, "changed": f"{action} {code}"}
    if action in ("also-allow-list", "block-wins"):
        flag = str(value).lower() in ("on", "true", "1", "yes")
        policy[action.replace("-", "_")] = flag
        return policy, {"ok": True, "changed": f"{action} -> {'on' if flag else 'off'}"}
    return policy, {"ok": False, "why": f"no such action: {action}"}


def explain(policy=None):
    """what the policy means in a sentence, so a human can check it says what they meant."""
    policy = policy or load()
    mode = policy["mode"]
    if mode == "open":
        base = "everybody can text the agent"
    elif mode == "list":
        n = len(policy["allow_numbers"])
        base = f"only the {n} number{'s' if n != 1 else ''} on the list can text the agent"
    elif mode == "local":
        base = (f"only numbers from {policy['home']} can text the agent" if policy.get("home")
                else "local mode has no home country set, so nobody gets in")
    else:
        allowed = ", ".join(policy["allow_countries"]) or "no countries"
        base = f"numbers from {allowed} can text the agent"
    extras = []
    if policy["block_countries"]:
        extras.append("never " + ", ".join(policy["block_countries"]))
    if policy["block_numbers"]:
        extras.append(f"{len(policy['block_numbers'])} blocked number(s)")
    if policy["also_allow_list"] and mode != "list" and policy["allow_numbers"]:
        extras.append("listed numbers always get in")
    extras.append("brand names and short codes get in" if mode == "open"
                  else "brand names and short codes are refused")
    return base + ("; " + "; ".join(extras) if extras else "")
