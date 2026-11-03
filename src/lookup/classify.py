"""classify: the line class of a number, from its market's numbering plan.

the plan is the evidence. a regulator publishes which ranges exist and what each is issued for, so "is
this a mobile" is a table lookup in the markets where that is true and an honest `unknown` in the ones
where it is not. the north american numbering plan is the important case of the second kind: line type
there is a carrier question, never a range question, so a +1 number comes back unknown and says why
instead of inferring a line type from an area code.

coverage is per market and named in MARKETS, because a lookup tool that quietly generalises from the one
plan it knows is worse than no tool.
"""
import json
import pathlib

from src.lookup import email as email_mod
from src.lookup import handles as handles_mod
from src.setup import numbering

NANP_FILE = pathlib.Path(__file__).with_name("nanp.json")
_NANP = None


def nanp():
    """the generated area code table, read once: the plan's geography, not a carrier's."""
    global _NANP
    if _NANP is None:
        try:
            _NANP = json.loads(NANP_FILE.read_text())
        except (OSError, ValueError):
            _NANP = {"countries": {}, "area_codes": {}, "_generated": {"from": "absent"}}
    return _NANP
PER_RANGE = "per-range"
MARKET_LEVEL = "market-level"
CARRIER_QUESTION = "carrier-question"
UNSEEDED = "unseeded"
AREA_CODE = "area-code"

STRENGTH = {
    PER_RANGE: "the plan encodes the line type for every range, so this is a table lookup: ofcom's "
               "numbering data for gb",
    MARKET_LEVEL: "this market issues cloud numbers in mobile ranges, which answers whether a number "
                  "from here is the right class, not which range this one is",
    CARRIER_QUESTION: "this market's plan does not encode line type. a carrier lookup answers that "
                      "question and a range lookup cannot, so the answer is unknown",
    UNSEEDED: "no numbering table for this market is carried here, so nothing is claimed about it",
    AREA_CODE: "the nanp assigns area codes to countries, territories and regions, so geography is a "
                "plan fact. it assigns no line type, which stays a carrier question",
}

MARKETS = {
    "GB": {"dial": "44", "strength": PER_RANGE, "source": "ofcom numbering data",
           "areas": {"20": "london", "23": "south coast", "24": "coventry",
                     "28": "northern ireland", "29": "cardiff", "113": "leeds", "114": "sheffield",
                     "115": "nottingham", "116": "leicester", "117": "bristol", "118": "reading",
                     "121": "birmingham", "131": "edinburgh", "141": "glasgow", "151": "liverpool",
                     "161": "manchester", "191": "tyneside"}},
    "US": {"dial": "1", "strength": CARRIER_QUESTION, "source": "nanp"},
    "CA": {"dial": "1", "strength": CARRIER_QUESTION, "source": "nanp"},
    "SE": {"dial": "46", "strength": MARKET_LEVEL, "source": "pts"},
    "PL": {"dial": "48", "strength": MARKET_LEVEL, "source": "uke"},
    "LT": {"dial": "370", "strength": MARKET_LEVEL, "source": "rrt"},
    "NL": {"dial": "31", "strength": MARKET_LEVEL, "source": "acm"},
    "AU": {"dial": "61", "strength": MARKET_LEVEL, "source": "acma"},
}

# what the range class says about a text arriving, which is the question behind most lookups
TEXT_BY_SMS = {"yes": True, "usually": True, "sometimes": "unknown", "no": False, "never": False}

NANP_TYPES = {"geographic": "unknown", "non-geographic": "non-geographic numbering",
              "toll-free": "toll-free", "premium": "premium rate",
              "personal numbering": "personal numbering"}

# what the area code class says about a text, which for a service code is the useful part
NANP_TEXT = {"geographic": "unknown", "non-geographic": "unknown", "toll-free": False,
             "premium": False, "personal numbering": "unlikely"}

# a field the plan cannot fill is not a hole in the output, it is part of the answer, so every answer
# says which fields it withheld and why. an empty region on a toll-free number is the plan being exact.
WITHHELD = {
    "toll-free": {"region": "a toll-free code is national by design: there is no region to give, and "
                            "the empty region is the answer rather than missing data",
                  "type": "the number belongs to whoever answers it, so a service line has no "
                          "personal line type"},
    "premium": {"region": "a premium rate code is national by design, so there is no region",
                "type": "a premium rate service is not a personal line"},
    "geographic": {"type": "the plan does not encode line type anywhere in it, so mobile, landline "
                           "and voip are indistinguishable from the number alone"},
    "non-geographic": {"region": "the plan marks this code as national rather than regional, so there "
                                 "is no region to give"},
    "personal numbering": {"region": "a personal numbering code is national rather than regional",
                           "type": "the number follows a person rather than a line, so the line type "
                                   "is not what it names"},
}

KINDS = {"mobile": "mobile", "business": "business numbering", "geographic": "landline",
         "voip": "voip", "personal numbering": "personal numbering", "pager": "pager",
         "service": "service range", "premium": "premium rate"}

# the markets where a plan cannot answer are the markets where somebody sells the answer. naming the
# adapter, and its cost, is more useful than shrugging at the question
ADAPTER = {"what": "a carrier lookup (twilio line type intelligence and its peers) returns mobile, "
                   "landline, fixed voip, non-fixed voip or unknown for one number",
           "wired": False,
           "consequence": "the number is handed to a third party and billed per lookup, which is why it "
                          "is not the default path for a question a plan cannot answer"}

LIMITS = {
    "porting": "a ported number keeps its range and changes its network",
    "person": "one number is not one human: shared landlines exist",
    "virtual": "most consumer voip apps draw numbers from ordinary national blocks, so a range "
               "cannot see them",
    "carrier": "the answer is about the range, never about the carrier holding it today",
}


def valid(number):
    """e164 shaped, which is the whole of the format claim: a plus and eight to fifteen digits."""
    text = str(number or "").strip()
    if not text.startswith("+"):
        return False
    return text[1:].isdigit() and 8 <= len(text[1:]) <= 15


def digits(number):
    return "".join(ch for ch in str(number or "") if ch.isdigit())


def market_of(number):
    got = digits(number)
    for iso, row in sorted(MARKETS.items(), key=lambda kv: -len(kv[1]["dial"])):
        if got.startswith(row["dial"]) and len(got) - len(row["dial"]) >= 7:
            return iso
    return None


def _gb(national):
    found = numbering.uk_range(national)
    if not found:
        return {"type": "unknown", "receive_text": "unknown", "region": None,
                "why": "the range is not one of the groups carried here"}
    answer = {"type": KINDS.get(found["kind"], found["kind"]), "kind": found["kind"],
              "receive_text": TEXT_BY_SMS.get(found["sms"], "unknown"),
              "prefix": found["prefix"], "why": found["why"],
              "orderable_here": found["kind"] in numbering.UK_ORDERABLE}
    answer["region"] = None
    if found["kind"] == "geographic":
        for prefix, name in sorted(MARKETS["GB"]["areas"].items(), key=lambda kv: -len(kv[0])):
            if national[1:].startswith(prefix):
                answer["region"] = name
                break
    return answer


def _nanp(number, iso_dial):
    """a +1 number: the plan gives the country, the territory and the region, and stops there."""
    table = nanp()
    got = digits(number)
    npa = got[1:4]
    row = table["area_codes"].get(npa)
    if not row:
        return {"type": "unknown", "receive_text": "unknown", "region": None, "npa": npa,
                "adapter": ADAPTER,
                "withheld": {"region": "the table does not carry this area code, so not even the place "
                                      "is claimed",
                             "type": "the plan does not encode line type anywhere in it"},
                "why": f"the area code {npa} is not one the carried table knows, so not even the place "
                       f"is claimed, and the plan never carries line type"}
    country = table["countries"].get(row["iso"], row["iso"])
    kind = row["class"]
    text = NANP_TEXT.get(kind, "unknown")
    region = row["place"] if kind == "geographic" else None
    why = {
        "geographic": f"{npa} is a geographic area code for {row['place']}. the plan still says nothing "
                      f"about whether this line is mobile, landline or voip",
        "non-geographic": f"{npa} is one of the plan's national rather than regional codes",
        "toll-free": f"{npa} is a toll-free service code: a business answers it, nobody signs up with it",
        "premium": f"{npa} is a premium rate service code",
        "personal numbering": f"{npa} is a personal numbering code: a follow-me number rather than a "
                              f"line somebody answers",
    }.get(kind, "the area code class says nothing about line type")
    return {"type": NANP_TYPES.get(kind, "unknown"), "receive_text": text,
            "country": row["iso"], "country_name": country, "region": region,
            "npa": npa, "npa_class": kind, "why": why,
            "withheld": dict(WITHHELD.get(kind, {})),
            "adapter": ADAPTER if kind == "geographic" else None}


PARTIAL = r"^\+1(\d{3})$"

# what the string is asking to be read as. one function, because guessing wrong is the difference
# between classifying a person's number and classifying their handle as one
PLATFORMS = ("signal", "whatsapp")


def kind_of(value, platform=None):
    got = str(value or "").strip()
    if platform in PLATFORMS:
        return "username"
    if not got:
        return "unknown"
    if got.startswith("+") or (got[0].isdigit() and sum(ch.isdigit() for ch in got) >= 5
                               and all(ch.isdigit() or ch in " -()." for ch in got)):
        return "number"
    if "@" in got:
        return "email"
    return "username"


def partial(number):
    """a +1 area code on its own, which is the smallest input that still answers the geography.

    the plan puts the country and the region in the first three digits, so a caller who does not want to
    hand over a whole number is not missing anything the plan could tell them. this is the lookup's
    version of preferring the domain to the local part.
    """
    import re
    found = re.match(PARTIAL, str(number or "").strip())
    if not found:
        return None
    table = nanp()
    npa = found.group(1)
    row = table["area_codes"].get(npa)
    answer = {"number": number, "valid": False, "partial": True, "npa": npa,
              "verified": False,
              "privacy": {"enough": "for a +1 number the area code alone carries the country and the "
                                    "region, so the subscriber digits are not needed for this answer",
                          "network": "no request leaves the machine"}}
    if not row:
        answer.update({"type": "unknown", "receive_text": "unknown", "market": None,
                       "why": f"the area code {npa} is not one the carried table knows"})
        return answer
    detail = _nanp("+1" + npa + "0000000", "1")
    answer.update({"market": detail.get("country"), "country_name": detail.get("country_name"),
                   "region": detail.get("region"), "type": detail.get("type"),
                   "receive_text": detail.get("receive_text"), "npa_class": detail.get("npa_class"),
                   "why": "an area code lookup: " + str(detail.get("why")),
                   "withheld": detail.get("withheld") or {}})
    return answer


def classify(number, platform=None):
    """what the evidence says, what it cannot say, and nothing beyond that.

    three inputs, one answer shape. a number is read from a numbering plan, an address from its own
    string plus the provider that issues it, a handle from the platform's published form. all three
    return evidence, a `withheld` map and an `unknown` that means unknown.
    """
    kind = kind_of(number, platform)
    if kind == "email":
        return email_mod.lookup(number)
    if kind == "username":
        return handles_mod.lookup(number, platform)
    iso = market_of(number) if valid(number) else None
    answer = {"number": number, "valid": valid(number), "market": iso, "verified": False,
              "limits": dict(LIMITS)}
    if not answer["valid"]:
        short = partial(number) if str(number or "").strip().startswith("+1") else None
        if short:
            return short
        answer.update({"type": "unknown", "receive_text": "unknown", "evidence": [],
                       "why": "not an e164 number, so there is nothing to classify"})
        return answer
    if not iso:
        answer.update({"type": "unknown", "receive_text": "unknown",
                       "withheld": {field: "no numbering table is carried for this market, so this is "
                                           "unanswered rather than guessed"
                                    for field in ("type", "receive_text", "region")},
                       "why": STRENGTH[UNSEEDED], "evidence": [{"strength": UNSEEDED}]})
        return answer
    row = MARKETS[iso]
    got = digits(number)
    if row["strength"] == PER_RANGE:
        national = "0" + got[len(row["dial"]):]
        detail = _gb(national)
    elif row["strength"] == CARRIER_QUESTION:
        detail = _nanp(number, row["dial"])
        answer["market"] = detail.get("country") or iso
        answer["plan"] = "NANP"
        answer["country_name"] = detail.get("country_name")
    else:
        detail = {"type": "mobile", "receive_text": True, "region": None,
                  "why": "cloud numbers in this market are issued in mobile ranges"}
    answer.update(detail)
    answer["privacy"] = {"derived_from": "the market's numbering plan, read locally",
                         "network": "no request leaves the machine",
                         "retention": "nothing is stored"}
    if row["strength"] == CARRIER_QUESTION:
        generated = nanp()["_generated"]
        answer["evidence"] = [
            {"strength": AREA_CODE, "source": f"{generated['from']} area code table, "
                                              f"generated {generated['at']}",
             "why": STRENGTH[AREA_CODE]},
            {"strength": CARRIER_QUESTION, "source": row["source"], "why": STRENGTH[CARRIER_QUESTION]}]
    else:
        answer["evidence"] = [{"strength": row["strength"], "source": row["source"],
                               "why": STRENGTH[row["strength"]]}]
    if detail.get("region") is None:
        answer.setdefault("withheld", {})
        answer["withheld"].setdefault("region", (
            "the range is not tied to a place, so the plan has no region for this number"
            if detail.get("type") not in ("landline", "business numbering", None)
            else "this market's table carries no region for this number"))
    answer["limits"]["coverage"] = (
        f"{iso} is carried per range from {row['source']}" if row["strength"] == PER_RANGE
        else f"{iso} is carried at {row['strength']} strength")
    return answer
