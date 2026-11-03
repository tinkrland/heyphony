"""numbering: what a prefix says about whether the number can hold a text.

a country code is not one product. inside the united kingdom, 07 is a mobile range and behaves like a
mobile, 03 is a business range that is usually sms capable, and 01 and 02 are geographic landlines that
mostly cannot receive a text at all. the same carrier, the same sip client and the same monthly price
sit behind all of them, so the prefix is the field that decides whether the text lane exists.

this module exists because "get a uk number" is not an instruction. the order has to name a range, and
the two ranges that work are 07 and 03.
"""

REFUSED = "refused"
STANDARD = "standard"
PRICIER = "pricier"

COUNTRIES = {
    "GB": {"name": "united kingdom", "code": "+44", "band": STANDARD,
           "order": "order a 07 mobile range, or an 03 business range with sms enabled",
           "avoid": "01 and 02 are geographic landlines and most of them cannot receive a text",
           "why": "ofcom issues virtual mobile numbers in mobile ranges, so a cloud number here is a "
                  "mobile number rather than a did"},
    "SE": {"name": "sweden", "code": "+46", "band": STANDARD,
           "order": "order a mobile range number", "avoid": "a geographic fixed line",
           "why": "the same class of number as the uk, at a normal price, which is why it is on the list"},
    "LT": {"name": "lithuania", "code": "+370", "band": STANDARD,
           "order": "order a mobile range number", "avoid": "a geographic fixed line",
           "why": "mobile ranges issued to providers, normal price"},
    "PL": {"name": "poland", "code": "+48", "band": STANDARD,
           "order": "order a mobile range number", "avoid": "a geographic fixed line",
           "why": "mobile ranges issued to providers, normal price"},
    "AU": {"name": "australia", "code": "+61", "band": PRICIER,
           "order": "order a mobile range number", "avoid": "a geographic fixed line",
           "why": "mobile ranges, and the price is the expensive part of this row"},
    "NL": {"name": "netherlands", "code": "+31", "band": PRICIER,
           "order": "order a mobile range number", "avoid": "a geographic fixed line",
           "why": "works the same way and costs the most of any row here"},
    "US": {"name": "united states", "code": "+1", "band": REFUSED,
           "order": "nothing to order: the class is the problem",
           "avoid": "the whole plan", "why": "cloud, softphone and trunk share one bucket and services read it as voip"},
    "CA": {"name": "canada", "code": "+1", "band": REFUSED,
           "order": "nothing to order: the class is the problem",
           "avoid": "the whole plan", "why": "same bucket as the united states"},
}

# the uk ranges, with the sms answer each one gives. a range is the product here, not the country.
UK_RANGES = [
    {"prefix": "071", "kind": "mobile", "sms": "yes", "why": "a mobile range, which is why a text arrives"},
    {"prefix": "072", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "073", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "074", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "075", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "077", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "078", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "079", "kind": "mobile", "sms": "yes", "why": "a mobile range"},
    {"prefix": "076", "kind": "pager", "sms": "no", "why": "paging, not messaging"},
    {"prefix": "070", "kind": "personal numbering", "sms": "no",
     "why": "personal numbering redirects a call, it does not hold a text"},
    {"prefix": "030", "kind": "business", "sms": "usually", "why": "a business range, and most carriers carry texts on it"},
    {"prefix": "033", "kind": "business", "sms": "usually", "why": "a business range, and most carriers carry texts on it"},
    {"prefix": "034", "kind": "business", "sms": "usually", "why": "a business range"},
    {"prefix": "037", "kind": "business", "sms": "usually", "why": "a business range"},
    {"prefix": "056", "kind": "voip", "sms": "no",
     "why": "056 is the uk's own range for voip services, so it is the one prefix that announces it"},
    {"prefix": "080", "kind": "freephone", "sms": "no", "why": "inbound only, and you cannot be texted on it"},
    {"prefix": "084", "kind": "service", "sms": "no", "why": "a service range, inbound charged"},
    {"prefix": "087", "kind": "service", "sms": "no", "why": "a service range, inbound charged"},
    {"prefix": "09", "kind": "premium", "sms": "never", "why": "premium rate, and not a number a person can text"},
]

UK_ORDERABLE = ("07", "03")


def _national(number):
    """digits only, with the uk trunk zero restored from e164, or None when it is not a number."""
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if not digits:
        return None, None
    if digits.startswith("44") and len(digits) >= 12:
        return "GB", "0" + digits[2:]
    if digits.startswith("0"):
        return "GB", digits
    return None, digits


def country_of(number):
    """the iso country a number belongs to, by the codes this repo has an opinion about."""
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    for iso, row in COUNTRIES.items():
        if digits.startswith(row["code"].lstrip("+")) and len(digits) >= 10:
            return iso
    return None


def uk_range(national):
    """the range row a uk national number belongs to, longest prefix first."""
    for row in sorted(UK_RANGES, key=lambda r: len(r["prefix"]), reverse=True):
        if national.startswith(row["prefix"]):
            return row
    if national.startswith(("01", "02")):
        return {"prefix": national[:2], "kind": "geographic", "sms": "no",
                "why": "a geographic landline range, and most of these cannot receive a text"}
    if national.startswith("05"):
        return {"prefix": national[:3], "kind": "corporate", "sms": "sometimes",
                "why": "corporate numbering, and whether a text lands is a carrier question"}
    return None


def look(number, country=None):
    """what this number's prefix says it is. always answers, and says when it does not know."""
    iso = country or country_of(number)
    _, national = _national(number)
    if not iso:
        return {"number": number, "country": None, "known": False,
                "why": "this module holds opinions about the uk, sweden, lithuania, poland, australia, "
                       "the netherlands and +1, and nothing about a number it cannot place"}
    row = COUNTRIES.get(iso)
    if national and iso == "GB":
        found = uk_range(national)
        if found:
            return {"number": number, "country": iso, "country_name": row["name"], "prefix": found["prefix"],
                    "kind": found["kind"], "sms": found["sms"],
                    "orderable": found["kind"] in ("mobile", "business"),
                    "known": True, "why": found["why"]}
    return {"number": number, "country": iso, "country_name": row["name"], "prefix": national,
            "kind": row["band"], "sms": "unknown", "orderable": row["band"] != REFUSED, "known": True,
            "why": row["why"]}


def advice(iso):
    """what to order for a country, in the words an agent can act on."""
    row = COUNTRIES.get((iso or "").upper())
    if not row:
        return {"country": iso, "known": False,
                "why": "no numbering opinion for that country", "countries": sorted(COUNTRIES)}
    return {"country": iso.upper(), "country_name": row["name"], "code": row["code"], "band": row["band"],
            "order": row["order"], "avoid": row["avoid"], "why": row["why"],
            "orderable_prefixes": list(UK_ORDERABLE) if iso.upper() == "GB" else None}


def warn(number):
    """one line when the number a person already holds cannot hold a text, or None when it is fine."""
    found = look(number)
    if not found.get("known") or found.get("sms") in ("yes", "usually", "unknown"):
        return None
    return {"number": number, "kind": found.get("kind"), "prefix": found.get("prefix"),
            "why": found.get("why"),
            "next": "the text lane will not exist on this range: order a 07 mobile or an 03 business "
                    "range, or keep this number for voice only"}
