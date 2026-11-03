"""classify: the line class of a number, from its market's numbering plan.

the plan is the evidence. a regulator publishes which ranges exist and what each is issued for, so "is
this a mobile" is a table lookup in the markets where that is true and an honest `unknown` in the ones
where it is not. the north american numbering plan is the important case of the second kind: line type
there is a carrier question, never a range question, so a +1 number comes back unknown and says why
instead of inferring a line type from an area code.

coverage is per market and named in MARKETS, because a lookup tool that quietly generalises from the one
plan it knows is worse than no tool.
"""
from src.setup import numbering

PER_RANGE = "per-range"
MARKET_LEVEL = "market-level"
CARRIER_QUESTION = "carrier-question"
UNSEEDED = "unseeded"

STRENGTH = {
    PER_RANGE: "the plan encodes the line type for every range, so this is a table lookup: ofcom's "
               "numbering data for gb",
    MARKET_LEVEL: "this market issues cloud numbers in mobile ranges, which answers whether a number "
                  "from here is the right class, not which range this one is",
    CARRIER_QUESTION: "this market's plan does not encode line type. a carrier lookup answers that "
                      "question and a range lookup cannot, so the answer is unknown",
    UNSEEDED: "no numbering table for this market is carried here, so nothing is claimed about it",
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


def classify(number):
    """what the evidence says, what it cannot say, and nothing beyond that."""
    iso = market_of(number) if valid(number) else None
    answer = {"number": number, "valid": valid(number), "market": iso, "verified": False,
              "limits": dict(LIMITS)}
    if not answer["valid"]:
        answer.update({"type": "unknown", "receive_text": "unknown", "evidence": [],
                       "why": "not an e164 number, so there is nothing to classify"})
        return answer
    if not iso:
        answer.update({"type": "unknown", "receive_text": "unknown",
                       "why": STRENGTH[UNSEEDED], "evidence": [{"strength": UNSEEDED}]})
        return answer
    row = MARKETS[iso]
    got = digits(number)
    if row["strength"] == PER_RANGE:
        national = "0" + got[len(row["dial"]):]
        detail = _gb(national)
    elif row["strength"] == CARRIER_QUESTION:
        detail = {"type": "unknown", "receive_text": "unknown", "region": None,
                  "why": "the plan does not separate mobile, landline and voip, so the range says "
                         "nothing about the line",
                  "adapter": ADAPTER}
    else:
        detail = {"type": "mobile", "receive_text": True, "region": None,
                  "why": "cloud numbers in this market are issued in mobile ranges"}
    answer.update(detail)
    answer["evidence"] = [{"strength": row["strength"], "source": row["source"],
                           "why": STRENGTH[row["strength"]]}]
    answer["limits"]["coverage"] = (
        f"{iso} is carried per range from {row['source']}" if row["strength"] == PER_RANGE
        else f"{iso} is carried at {row['strength']} strength")
    return answer
