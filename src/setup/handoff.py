"""the human acts, and where they actually happen.

until now every step that a person has to do was a sentence: "fetch the sip credentials", "confirm the
did is sms capable". somebody who has never opened voip.ms reads that and has no idea which menu it is,
so the honest fix is not more prose. it is a link, the name of the control as that vendor labels it, and
the exact string to copy back and where it lands.

this file is that, per vendor, written once so the cli, the plan and the pages read the same rows rather
than three descriptions of the same click.

what this deliberately does not claim: that a portal looks like this today. the entrances are the
vendors' own published urls, the section names are the vendors', and every row is `verified: false`
because nobody in this repo has clicked any of them with a real account. a moved page is then a link to
fix rather than a secret somebody lost.
"""

from src.setup import routes

# the entrances. base is the portal, docs is the vendor's own page for the thing being asked, and both
# come from the vendor rather than from a guess, which is why they are one table instead of prose.
ENTRANCES = {
    "voip.ms": {
        "portal": "https://voip.ms",
        "docs": "https://voip.ms/m/api.php",
        "number": "DID Numbers",
        "sip": "Sub Accounts",
        "texts": "SMS / Messaging",
        "mail": "SMS to Email (under the DID's messaging settings)",
    },
    "flowroute": {
        "portal": "https://manage.flowroute.com",
        "docs": "https://developer.flowroute.com/docs",
        "number": "Numbers",
        "sip": "Credentials (under Interconnection)",
        "texts": "Inbound Routes, then SMS",
        "mail": None,
    },
    "anveo": {
        "portal": "https://www.anveo.com",
        "docs": "https://www.anveo.com/api.asp",
        "number": "My Numbers",
        "sip": "SIP Devices / Accounts",
        "texts": "the DID's SMS URL field (or DID.UPDATE over the api)",
        "mail": None,
    },
    "signalwire": {
        "portal": "https://signalwire.com",
        "docs": "https://developer.signalwire.com",
        "number": "Phone Numbers",
        "sip": "SIP / Credentials under the Space",
        "texts": "the number's message handler",
        "mail": None,
    },
    "questblue": {
        "portal": "https://customer.questblue.com",
        "docs": "https://customer.questblue.com",
        "number": "DIDs",
        "sip": "Trunks",
        "texts": "SMS v2 mode (sms_mode=url, post2urlmethod=json)",
        "mail": "message relay: email, xmpp or a pbx host",
    },
    "bulkvs": {
        "portal": "https://portal.bulkvs.com",
        "docs": "https://portal.bulkvs.com/api/v1.0/openapi",
        "number": "DIDs",
        "sip": "Subaccounts",
        "texts": "Webhooks (one url, then attach it to numbers)",
        "mail": None,
    },
    "jmp.chat": {
        "portal": "https://jmp.chat",
        "docs": "https://jmp.chat",
        "number": "plans / your number",
        "sip": "the app's own account (no sip password is issued)",
        "texts": "the XMPP/Jabber inbox: there is no webhook to arm",
        "mail": "the inbox is XMPP, which is also why the catcher cannot receive it",
    },
    "voyced": {
        "portal": "https://www.voyced.com",
        "docs": "https://www.voyced.com",
        "number": "Numbers",
        "sip": "SIP accounts",
        "texts": "no sms url is documented, so nothing to arm yet",
        "mail": None,
    },
    "voxacall": {
        "portal": "https://voxacall.com",
        "docs": "https://voxacall.com",
        "number": "Numbers",
        "sip": "Trunks / SIP accounts",
        "texts": "nothing public: no sms url documented",
        "mail": None,
    },
    "bitcall": {
        "portal": "https://bitcall.io",
        "docs": "https://bitcall.io",
        "number": "DID inventory is advertised as coming soon",
        "sip": "API keys (otp / esim / hlr today)",
        "texts": "no inbound sms claim",
        "mail": None,
    },
}

# every row below is one human act: what to do, where, what to copy back, and which key it becomes.
# the shapes are the vendors' words where the vendor publishes them, and "ask support" where it does not,
# because inventing a menu name is how somebody spends an hour looking for a page that never existed.
ACTS = {
    "voip.ms": [
        {"act": "buy or point one did at this host", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "an sms capable did is the whole product; a voice only number fails weeks later"},
        {"act": "create a sub account, which is the sip identity", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "one registration, one secret, written by `heyphony connect sip --voipms`"},
        {"act": "enable sms on the number and make it go to email", "copy": "the mailbox it lands in",
         "lands_in": "the email lane, not the sip client", "section": "mail",
         "why": "voip.ms delivers texts by email, so there is no url to arm and texts never ride sip"},
    ],
    "flowroute": [
        {"act": "buy or point one did at this host", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "one number, one agent, which is the shape this repo is for"},
        {"act": "create interconnection credentials", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "the registration baresip makes, and the only thing that makes a call ring"},
        {"act": "arm an inbound sms route at the url below", "copy": "nothing: paste the url",
         "lands_in": "the paste url from `heyphony hooks flowroute --template`", "section": "texts",
         "why": "flowroute posts json to a url; the catcher has the same url in its route table"},
    ],
    "anveo": [
        {"act": "buy or point one did at this host", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "anveo is also the one vendor the repo can order from, with payment parked on purpose"},
        {"act": "create a sip device for the number", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "a device, not a sub account: the word differs and the values do not"},
        {"act": "set the did's sms url, or let DID.UPDATE do it", "copy": "nothing: paste the url",
         "lands_in": "anveo's SMS_URL, set by `heyphony hooks anveo --apply`", "section": "texts",
         "why": "the only vendor here whose hook can be armed over the api without a portal visit"},
    ],
    "signalwire": [
        {"act": "buy or point one did at the space", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "the cheapest did of the ten, and billed per inbound message"},
        {"act": "create sip credentials in the space", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "registration, same as the others, with a different menu"},
        {"act": "set the number's message handler to the url below", "copy": "nothing: paste the url",
         "lands_in": "the message handler resource", "section": "texts",
         "why": "the handler resource path is not verified here, which the template says out loud"},
    ],
    "questblue": [
        {"act": "buy or point one did at the account", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "questblue trunks route rather than register, so the did comes with the route"},
        {"act": "create a trunk with sip credentials", "copy": "the three credentials",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "trunk, not registration: three values, and the page says which is which"},
        {"act": "set sms v2 mode to url with json posting", "copy": "nothing: paste the url",
         "lands_in": "sms_mode=url and post2urlmethod=json, or the api call the template shows",
         "section": "texts",
         "why": "the only vendor here that needs two settings rather than one"},
        {"act": "or relay messages to a mailbox instead", "copy": "the mailbox address",
         "lands_in": "the email lane, read by `heyphony import --file`", "section": "mail",
         "why": "a relay is a re-send: the reply thread is the carrier's, not this repo's"},
    ],
    "bulkvs": [
        {"act": "buy or point one did at the account", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "six cents a month, which is the cheapest number in the table"},
        {"act": "create a subaccount", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "registration, and the subaccount is what baresip registers as"},
        {"act": "register one webhook, then attach it to the number", "copy": "nothing: paste the url",
         "lands_in": "the Webhooks resource, one url for the account", "section": "texts",
         "why": "one url registered once and attached to numbers, so the same address serves a second did"},
    ],
    "jmp.chat": [
        {"act": "subscribe and keep the jabber id", "copy": "the did, which here is an xmpp address and not a phone number",
         "lands_in": "nothing in this repo: the inbox is XMPP", "section": "number",
         "why": "there is no webhook and no sip password, so the catcher cannot receive this one"},
        {"act": "point an xmpp client at the inbox",
         "copy": "the sip password this vendor does not issue: the xmpp app password instead",
         "lands_in": "the xmpp client, not baresip's sip config", "section": "sip",
         "why": "honest: this vendor is in the table to say where the shape stops"},
    ],
    "voyced": [
        {"act": "order a number", "copy": "the number, in e164",
         "lands_in": "HEYPHONY_DID", "section": "number",
         "why": "eu voice is its strength; inbound sms is not documented"},
        {"act": "create a sip account", "copy": "username and password",
         "lands_in": "the sip section of the 0600 config", "section": "sip",
         "why": "registration works even where texts do not, which is worth knowing before buying"},
    ],
    "voxacall": [
        {"act": "order a number and a trunk", "copy": "the number, the trunk credentials",
         "lands_in": "HEYPHONY_DID and the sip section", "section": "number",
         "why": "a crypto-native trunk, and nothing public about sms"},
        {"act": "ask support for the sms url field", "copy": "whatever they answer",
         "lands_in": "nowhere until it is documented", "section": "texts",
         "why": "no sms url is documented, so the template refuses rather than guesses"},
    ],
    "bitcall": [
        {"act": "use the api for codes and lookups", "copy": "the did, when inventory stops saying coming soon",
         "lands_in": "the api key env for the lookup rail", "section": "sip",
         "why": "otp, esim and hlr are the product; dids are advertised as coming soon"},
        {"act": "do not plan on a number or a sip registration here yet",
         "copy": "no sip username exists to ask for: this vendor sells api calls, not a line",
         "lands_in": "nothing in this repo, which is the honest answer until inventory ships",
         "section": "number",
         "why": "a row in the table that says no, which is more useful than a row that is missing"},
    ],
}

# which act is the one that makes texts arrive, per kind of route. this is the join between handoff and
# routes: the vendor's own route decides whether the answer is a url to paste or a mailbox to point.
TEXTS_BY_KIND = {
    "webhook-json": "paste the url from the template as the inbound sms destination",
    "url-forward": "paste the url from the template into the did's sms url field",
    "post-to-url": "paste the url from the template, and set the vendor's post mode to json",
    "email": "point the vendor's sms-to-email at the email lane: no url is posted",
    "xmpp": "no webhook exists, so the inbox is a jabber client, not this repo",
    "none": "the vendor documents no inbound sms, so there is nothing to arm yet",
}


def entrance(provider):
    """the vendor's own doors, refused by name if it is not one of the ten."""
    name = _name(provider)
    return ENTRANCES[name]


def acts(provider):
    """the human acts for one vendor, each with a link, a section and where the value lands."""
    name = _name(provider)
    doors = ENTRANCES[name]
    route = routes.ROUTES[name]
    out = []
    for number, act in enumerate(ACTS[name], start=1):
        section = act["section"]
        label = doors.get(section)
        out.append({
            "n": number,
            "act": act["act"],
            "where": doors["portal"],
            "section": label,
            "copy": act["copy"],
            "lands_in": act["lands_in"],
            "why": act["why"],
            "docs": doors["docs"],
            "how_texts_arrive": TEXTS_BY_KIND.get(route["kind"]),
            "verified": False,
        })
    return out


def links(provider=None):
    """the acts for one vendor, or every vendor, with the count so a caller can tell it is not empty."""
    names = [_name(provider)] if provider else list(ENTRANCES)
    return {
        "ok": True,
        "providers": {name: {"portal": ENTRANCES[name]["portal"], "acts": acts(name)} for name in names},
        "counts": {name: len(ACTS[name]) for name in names},
        "verified": False,
        "means": ("a click and a copy per act, because 'fetch the sip credentials' is not an instruction "
                  "to somebody who has never seen the portal. the links are the vendors' own entrances"),
        "unknown": ("no portal in this repo has been clicked with a real account, so a section name may "
                    "have moved; the docs url is the vendor's own page for the same thing"),
    }


def template(provider, base="https://your-host:8099"):
    """one vendor's arm-the-hook template: a url, a method, a sample the parser is checked against.

    the sample body is derived from the route's own parse map rather than written by hand, so the thing a
    person pastes and the thing the catcher expects cannot drift apart without a test failing.
    """
    name = _name(provider)
    route = routes.ROUTES[name]
    kind = route["kind"]
    hook = routes.hook(name, base=base)
    http = kind in ("webhook-json", "url-forward", "post-to-url")

    bare, _, query = (hook["paste_url"] or "").partition("?")
    out = {
        "provider": name,
        "kind": kind,
        "url": bare if http else None,
        # a url-forward vendor fills these itself: they are the vendor's placeholder syntax, shown so a
        # person can see what will arrive rather than discovering it in the first stored message
        "placeholders": query or None,
        "method": "POST" if http else None,
        "content_type": "application/json" if kind in ("webhook-json", "post-to-url") else (
            "form or query, as the vendor sends it" if kind == "url-forward" else None),
        "paste_where": ENTRANCES[name].get("texts"),
        "configure": route["configure"],
        "sample": _sample(name) if http else None,
        "verify": _verify(name, bare) if http else None,
        "arming": route.get("apply"),
        "cli": "heyphony hooks {} --base {}".format(name, base),
        "email_instead": _mail(name, route),
        "verified": False,
        "evidence": route.get("evidence"),
    }
    if not http:
        out["instead"] = {
            "email": "point sms-to-email at the email lane and run `heyphony import --file <saved message>`",
            "xmpp": "run an xmpp client against the inbox: no http path exists to catch",
            "none": "nothing to arm: this vendor documents no inbound sms",
        }[kind]
    return out


def _sample(provider):
    """a body built from the route's own parse map, so a rename in one lands as a failure in the other."""
    parse = routes.ROUTES[provider].get("parse") or {}
    values = {"sender": "+15550000001", "recipient": "+15550000002", "body": "hello from the template",
              "id": "template-1", "at": "2026-01-01T00:00:00Z",
              "media": ["https://carrier.example/m/1.jpg"]}
    body = {}
    for field, aliases in parse.items():
        if not aliases:
            continue
        body[aliases[0]] = values.get(field, "value")
    return body or None


def _verify(provider, url):
    """the one line that proves a template reached the catcher, which is the only proof on offer here."""
    return ("curl -sS -X POST {} -H 'Content-Type: application/json' -d '{}'"
            .format(url, _json(_sample(provider) or {})))


def _json(value):
    import json
    return json.dumps(value, separators=(",", ":"))


def _mail(provider, route):
    """the email-inbox route for the vendors that have one, and a plain no where they do not."""
    doors = ENTRANCES[provider]
    if doors.get("mail"):
        return {"where": doors["portal"], "section": doors["mail"],
                "lands_in": "the email lane, read by `heyphony import --file`",
                "why": "a relay re-sends: the recipient sees this number and the original sender sees silence",
                "verified": False}
    if route["kind"] == "email":
        return {"where": doors["portal"], "section": "sms to email",
                "lands_in": "the email lane", "why": "this vendor delivers texts by email", "verified": False}
    return None


def _name(provider):
    name = str(provider or "").strip()
    if name not in ENTRANCES:
        raise KeyError("unknown provider: {}; known: {}".format(name, ", ".join(ENTRANCES)))
    return name


def open_links(providers, opener=None):
    """open the portal for each vendor, and say so honestly when there is no browser to open it in.

    this is the one place a cli talks to a desktop, so it is also the one place that has to admit a
    server has no screen. nothing is opened without being named in the payload first.
    """
    names = [_name(p) for p in providers] or list(ENTRANCES)
    urls = [ENTRANCES[name]["portal"] for name in names]
    if opener is None:
        import webbrowser
        opener = webbrowser.open
    opened = []
    for name, url in zip(names, urls):
        try:
            opened.append({"provider": name, "url": url, "opened": bool(opener(url))})
        except Exception as error:  # a headless box raises or returns False, and both are answers
            opened.append({"provider": name, "url": url, "opened": False, "why": str(error)})
    return {"opened": opened,
            "any": any(row["opened"] for row in opened),
            "means": ("a portal in a browser is not a step this repo can take for somebody; it can only "
                      "put the right page in front of them and say what to copy back"),
            "without_a_browser": ("on a server there is no page to open, so the urls in this payload are the "
                                  "whole answer: open them from a phone or a laptop with the same account")}
