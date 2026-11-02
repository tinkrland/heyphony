"""buying a number from the command line, where a provider actually allows it.

anveo is the one of the ten where the whole chain is documented enough to script:
ANVEO.AREAS.LIST tells you which area codes have stock and what each rate plan
costs, DID.ORDER places the order and answers with the numbers it bought, and
DID.UPDATE sets SMS_URL on a number by e164, which is the same url the catcher is
already listening on. so the same cli that explains a number can also get one,
and arm its texts before anyone opens a browser.

two things about their docs worth knowing before reading the code: the request
examples use api/v2.asp while the prose says api/v3.asp, and we call v3.asp
because it is the one the working examples in their own sample calls use. and
every request needs a SIGNATURE, which is not an api secret but
hmac_sha1(key=secure phrase, message=account email), so it can be computed here
instead of pasted. the test suite pins their published example vector.
"""
import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://www.anveo.com/api/v3.asp"
ENV = {"userkey": "ANVEO_USERKEY", "email": "ANVEO_EMAIL", "phrase": "ANVEO_SECURE_PHRASE"}
RATE_PLANS = {"SU": "service unlimited", "PU": "personal unlimited", "OU": "office unlimited",
              "VALUE": "value"}
DID_TYPES = ("GEOGRAPHIC", "NATIONAL", "TOLLFREE", "MOBILE")


def signature(email, phrase):
    """hmac_sha1(key=secure phrase, message=email), hex. their documented vector is the test."""
    return hmac.new(phrase.encode(), email.encode(), hashlib.sha1).hexdigest()


def missing():
    return [k for k, v in ENV.items() if not os.environ.get(v)]


def _query(action, params, test=False):
    query = {"userkey": os.environ.get(ENV["userkey"], ""), "action": action,
             "param[SIGNATURE]": signature(os.environ.get(ENV["email"], ""),
                                           os.environ.get(ENV["phrase"], ""))}
    if test:
        query["param[TEST]"] = "TRUE"
    for key, value in (params or {}).items():
        if value is not None:
            query[f"param[{key}]"] = str(value)
    return query


def as_curl(action, params=None, test=False):
    return f"curl -s '{BASE}?{urllib.parse.urlencode(_query(action, params, test))}'"


def parse(text):
    """their answers are xml: RESULT plus whatever nodes the action returns."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"result": None, "raw": text[:600]}
    out = {"result": (root.findtext("RESULT") or "").strip() or None}
    areas = [dict(node.attrib) | {"rate_plans": [dict(rp.attrib) for rp in node]}
             for node in root.iter("AREA")]
    dids = [dict(node.attrib) for node in root.iter("DID")]
    if areas:
        out["areas"] = areas
    if dids:
        out["dids"] = dids
    if not areas and not dids:
        out["raw"] = text[:600]
    return out


def call(action, params=None, test=False, timeout=25):
    gaps = missing()
    if gaps:
        return {"ok": False, "action": action, "missing": gaps,
                "why": "no anveo credentials in the environment, so nothing was sent",
                "as_curl": as_curl(action, params, test)}
    url = f"{BASE}?{urllib.parse.urlencode(_query(action, params, test))}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as answer:
            text = answer.read().decode("utf-8", "replace")
            return {"ok": True, "action": action, "status": answer.status, **parse(text)}
    except Exception as exc:  # their error text is more useful than our traceback
        return {"ok": False, "action": action, "why": f"anveo refused: {exc}"}


def areas(did_type="GEOGRAPHIC", country_id=None, state_id=None, area_code=None, area_name=None):
    """which area codes have stock, and what each rate plan costs in cents a month.

    "some number in your country" is not good enough for a number a human will be called back on, so
    area code and area name are first class filters rather than something to grep out of a list.
    """
    answer = call("ANVEO.AREAS.LIST", {"DID_TYPE": did_type, "COUNTRY_ID": country_id,
                                       "STATE_ID": state_id})
    if not answer.get("ok"):
        return answer
    rows = answer.get("areas", [])
    if area_code:
        rows = [a for a in rows if str(a.get("AREA_CODE")) == str(area_code)]
    if area_name:
        want = str(area_name).strip().lower()
        rows = [a for a in rows if want in str(a.get("AREA_NAME", "")).lower()]
    answer["areas"] = [_area_row(a) for a in rows]
    answer["filters"] = {"area_code": area_code, "area_name": area_name,
                         "country_id": country_id, "state_id": state_id, "did_type": did_type}
    answer["count"] = len(answer["areas"])
    return answer


def areas_menu(area_code=None, area_name=None, country_id=None, state_id=None,
               did_type="GEOGRAPHIC", env=None):
    """the lookup an agent runs before it can be asked which area code it wants.

    it never invents a list: without credentials the answer is closed and names what is missing,
    which is the same rule every other lane follows. with credentials it is a filtered list of
    area codes with stock and a price per rate plan, ordered so the affordable stock is first.
    """
    import os
    env = env if env is not None else os.environ
    missing_keys = [k for k in ("ANVEO_USERKEY", "ANVEO_EMAIL", "ANVEO_SECURE_PHRASE") if not env.get(k)]
    filters = {"area_code": area_code, "area_name": area_name, "country_id": country_id,
               "state_id": state_id, "did_type": did_type}
    if missing_keys:
        return {"ok": False, "closed": True, "missing": missing_keys, "filters": filters,
                "why": "anveo's area lookup is an authenticated call, so no list is shown until it can be made",
                "windows": ["call it with ANVEO_USERKEY, ANVEO_EMAIL and ANVEO_SECURE_PHRASE set "
                            "to see area codes with stock and price",
                            "anveo's portal lists the same areas if you would rather look at a table"]}
    answer = areas(did_type=did_type, country_id=country_id, state_id=state_id,
                   area_code=area_code, area_name=area_name)
    if not answer.get("ok"):
        return answer
    rows = answer.get("areas", [])
    rows = sorted(rows, key=lambda r: (r.get("stock") is None, -(r.get("stock") or 0),
                                       str(r.get("area_code"))))
    cheapest = None
    for row in rows:
        for plan in row.get("rate_plans", []):
            if plan.get("monthly_usd") is not None:
                cheapest = plan["monthly_usd"] if cheapest is None else min(cheapest, plan["monthly_usd"])
    answer["areas"] = rows
    answer["count"] = len(rows)
    answer["cheapest_monthly_usd"] = cheapest
    answer["next"] = ("heyphony setup provision --provider anveo --area-code <code> --apply"
                      if rows else "no stock for that filter: widen it, or try a neighbouring area name")
    return answer


def _area_row(area):
    """one area, with its rate plans as cents-a-month integers rather than strings."""
    plans = []
    for plan in area.get("rate_plans", []):
        plans.append({"id": plan.get("RATE_PLAN_ID"), "name": plan.get("RATE_PLAN_NAME"),
                      "monthly_usd": _cents(plan.get("MONTHLY100")), "setup_usd": _cents(plan.get("SETUP100"))})
    return {"area_id": area.get("AREA_ID"), "area_code": area.get("AREA_CODE"),
            "area_name": area.get("AREA_NAME"), "stock": _int(area.get("STOCK")), "rate_plans": plans}


def _cents(value):
    try:
        return round(int(value) / 100, 2)
    except (TypeError, ValueError):
        return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def order(did_type="GEOGRAPHIC", area_id=None, rate_plan="SU", title="heyphony", quantity=1, test=False):
    """place the order. without apply this is only ever a plan, because it spends money."""
    return call("DID.ORDER", {"DID_TYPE": did_type, "AREA_ID": area_id, "RATE_PLAN_ID": rate_plan,
                              "QUANTITY": quantity, "TITLE": title}, test=test)


def arm_sms(did, url, test=False):
    """point a number's incoming texts at a url, which is the hook the catcher serves."""
    return call("DID.UPDATE", {"FILTER.E164": str(did).lstrip("+"), "SMS_URL": url}, test=test)


def list_dids(did=None):
    return call("DID.LIST", {"FILTER.E164": str(did).lstrip("+")} if did else {})


def plan(area_code=None, did_type="GEOGRAPHIC", rate_plan="SU", sms_url=None, title="heyphony",
         apply=False, test=False, country_id=None, state_id=None, area_name=None, purchase=False):
    """the whole chain, as a plan an agent can read, or as the free steps it would actually run.

    apply stops at the last step on purpose: area stock and prices are free to ask for, DID.ORDER bills
    the account, and an agent that can spend money is a different product with a different consent
    story. so the order is *prepared* rather than placed, and purchase is parked rather than forgotten.
    """
    if str(did_type).upper() not in DID_TYPES:
        return {"ok": False, "why": f"did_type must be one of {', '.join(DID_TYPES)}", "provider": "anveo"}
    dtype = str(did_type).upper()
    filters = {"DID_TYPE": dtype, "COUNTRY_ID": country_id, "STATE_ID": state_id}
    order_params = {"DID_TYPE": dtype, "AREA_ID": "<from the first step>", "RATE_PLAN_ID": rate_plan,
                    "QUANTITY": 1, "TITLE": title}
    steps = [
        {"step": "find an area with stock", "action": "ANVEO.AREAS.LIST", "free": True,
         "params": filters, "as_curl": as_curl("ANVEO.AREAS.LIST", filters)},
        {"step": "buy one number", "action": "DID.ORDER", "free": False,
         "params": order_params, "as_curl": as_curl("DID.ORDER", order_params, test)},
        {"step": "point its texts at the catcher", "action": "DID.UPDATE", "free": True,
         "params": {"FILTER.E164": "<the did the order answered with>", "SMS_URL": sms_url or "<paste url>"},
         "as_curl": as_curl("DID.UPDATE", {"FILTER.E164": "<did>", "SMS_URL": sms_url or "<paste url>"})},
    ]
    answer = {"provider": "anveo", "did_type": dtype, "area_code": str(area_code) if area_code else None,
              "area_name": area_name, "rate_plan": rate_plan, "rate_plan_name": RATE_PLANS.get(str(rate_plan).upper()),
              "sms_url": sms_url, "steps": steps, "test_mode": bool(test),
              "missing": missing(), "applied": False, "verified": False,
              "note": "anveo is the one provider here whose whole chain is a documented api, which is why this "
                      "is a cli path and not a browser errand"}
    if purchase:
        return {**answer, "ok": False, "purchase": "parked",
                "why": "the order is the payment step, and no payment rail is wired here on purpose: an agent "
                       "that can spend money is a different product with a different consent story",
                "instead": "run the DID.ORDER call yourself, or order in the portal, then "
                           "`heyphony hooks anveo --apply --did <the number>`"}
    if not apply:
        answer["next"] = (f"heyphony setup provision --provider anveo"
                          f"{' --area-code ' + str(area_code) if area_code else ' --areas --country-id US'}"
                          " --apply    # free steps only: stock and prices, then the prepared order")
        return answer

    gaps = missing()
    if gaps:
        return {**answer, "ok": False, "missing": gaps,
                "why": "no anveo credentials in the environment, so nothing was asked of them"}
    found = areas(did_type=dtype, country_id=country_id, state_id=state_id,
                  area_code=area_code, area_name=area_name)
    if not found.get("ok"):
        return {**answer, "ok": False, "why": "the area lookup failed",
                "areas_answer": {k: v for k, v in found.items() if k != "areas"}}
    picked = found["areas"][0] if found.get("areas") else None
    answer.update({"ok": bool(picked), "areas": found["areas"][:25], "count": found.get("count"),
                   "matches": found.get("areas", [])[:25] if area_name or area_code else None})
    if not picked:
        answer["why"] = "no area matched that filter, so there was nothing to prepare an order for"
        return answer
    order_params = {"DID_TYPE": dtype, "AREA_ID": picked["area_id"], "RATE_PLAN_ID": rate_plan,
                    "QUANTITY": 1, "TITLE": title}
    answer.update({"ok": True, "picked": picked, "applied": True, "did": None,
                   "stopped_before": "DID.ORDER",
                   "why": "the order bills the account, so it is prepared here and not placed",
                   "order_call": as_curl("DID.ORDER", order_params, test),
                   "order_params": order_params,
                   "then": "run that call with your own key, or order the same area in the portal, then "
                           "`heyphony hooks anveo --apply --did <the number>` to arm its texts"})
    return answer
