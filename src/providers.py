"""providers as data.

the card's claims about what still works while the machine is off come from
here, so they cannot drift into a sales sentence: each capability is a value,
and anything not confirmed by a real delivery is marked unverified.

every provider also differs in three ways that matter more than the price: the
shape of its sip identity (registering a device, or routing a number at a trunk),
the way a text reaches us (a signed json webhook, a url with placeholders, a
post to url configured over their api, or an email), and whether a number can be
ordered over an api rather than a shopping cart. those are the keys text_style,
sip_style and api, and routes.py turns them into the actual wiring.
"""

PROVIDERS = {
    "voip.ms": {
        "provider": "voip.ms",
        "did_usd_month": 1.0,
        "text_style": "email",
        "sip_style": "registration",
        "api": {"ordering": True, "docs": "https://voip.ms/m/api.php", "note": "dids and sub accounts over rest"},
        "inbound_texts": "email, via carrier sms-to-email",
        "voicemail": "email, via carrier voicemail-to-email",
        "forwarding": "conditional, configured at the carrier",
        "server": "regional: atlanta, chicago, toronto, and others",
        "works_while_off": {"texts": True, "voicemail": True, "live_calls": False},
        "verified": False,
        "note": "the carrier catches what the machine cannot. live calls still need a registered endpoint.",
    },
    "flowroute": {
        "provider": "flowroute",
        "did_usd_month": 1.0,
        "text_style": "webhook-json",
        "sip_style": "registration",
        "api": {"ordering": True, "docs": "https://developer.flowroute.com", "note": "numbers and routes over rest"},
        "inbound_texts": "webhook or smpp, never sip",
        "voicemail": None,
        "forwarding": "not relied on here",
        "server": "sip registration host, see the dashboard",
        "works_while_off": {"texts": True, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "texts survive an off machine only because our webhook stores them. calls have no fallback.",
    },
    "anveo": {
        "provider": "anveo",
        "did_usd_month": 0.99,
        "plans_usd_month": {"per minute": 0.99, "personal unlimited": 4.00, "office unlimited": 7.00},
        "inbound_calls_usd_min": 0.01,
        "text_style": "url-forward",
        "sip_style": "registration",
        "api": {"ordering": True, "docs": "https://www.anveo.com/api.asp",
                "note": "DID.ORDER, DID.LIST and DID.UPDATE over api/v1.asp with an apikey"},
        "inbound_texts": "forwarded to a url with $[from]$ / $[to]$ / $[message]$ placeholders, or delivered over sip as a MESSAGE or INVITE",
        "voicemail": "call flow voicemail, transcribable",
        "forwarding": "call flow, drag and drop",
        "server": "sip registration, credentials from the dashboard device page",
        "works_while_off": {"texts": True, "voicemail": True, "live_calls": False},
        "verified": False,
        "note": "sms is per number and per country: us, canada and uk numbers receive texts, and the per minute plan charges a cent a minute for a live call.",
    },
    "signalwire": {
        "provider": "signalwire",
        "did_usd_month": 0.50,
        "tollfree_usd_month": 0.80,
        "inbound_text_usd": {"min": 0.0035, "max": 0.0040},
        "text_style": "webhook-json",
        "sip_style": "registration",
        "api": {"ordering": True, "docs": "https://signalwire.com/docs",
                "note": "sip credentials and phone numbers are rest resources in fabric"},
        "inbound_texts": "a swml message handler posts json to your url, or the compatibility api posts form fields",
        "voicemail": None,
        "forwarding": "a call handler decides, there is no carrier mailbox we lean on",
        "server": "username@your-space.sip.signalwire.com, with a password you choose",
        "works_while_off": {"texts": True, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "the cheapest did here at fifty cents, but inbound texts are not free: the rate card is per carrier, about a third of a cent to four tenths.",
    },
    "questblue": {
        "provider": "questblue",
        "did_usd_month": 0.70,
        "tollfree_usd_month": 0.75,
        "inbound_voice_usd_min": 0.009,
        "outbound_voice_usd_min": 0.009,
        "outbound_sms_usd": 0.010,
        "outbound_mms_usd": 0.015,
        "text_style": "post-to-url",
        "sip_style": "trunk-route",
        "api": {"ordering": True, "docs": "https://docs.questblue.com", "base": "https://api.questblue.com",
                "auth": "http basic plus a Security-Key header"},
        "inbound_texts": "per number sms mode: post to a url as form, json or xml, or forward to email, xmpp, 3cx or yeastar",
        "voicemail": None,
        "forwarding": "the did is pointed at an active sip trunk",
        "server": "no per-did registration: route2trunk points the number at a trunk",
        "works_while_off": {"texts": True, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "a trunk provider, not a softphone shop: the number is routed at your trunk, and a2p registration is the account's job.",
    },
    "bulkvs": {
        "provider": "bulkvs",
        "did_usd_month": 0.06,
        "tollfree_usd_month": 0.14,
        "inbound_voice_usd_min": 0.0003,
        "outbound_voice_usd_min": 0.004,
        "inbound_text_usd": {"min": 0.003, "max": 0.003},
        "outbound_sms_usd": 0.006,
        "sms_enablement_usd": 0.01,
        "text_style": "webhook-json",
        "sip_style": "registration",
        "api": {"ordering": True, "docs": "https://portal.bulkvs.com/api/v1.0/documentation",
                "base": "https://portal.bulkvs.com/api/v1.0",
                "note": "/orderTn, /tnRecord with a Webhook per number, and /webHooks to register the url"},
        "inbound_texts": "websocket-free webhook: one url registered over the api, per number",
        "voicemail": None,
        "forwarding": "call forward or failover on the number record",
        "server": "sip registration against their trunk groups",
        "works_while_off": {"texts": True, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "the cheapest row on this table and the only one with a per-number webhook in its api, but it sells north american numbers: the owner remembered uk coverage, and nothing on their own number search or pricing page backs that, so check before planning on it.",
    },
    "jmp.chat": {
        "provider": "jmp.chat",
        "did_usd_month": 4.99,
        "inbound_calls_usd_min": 0.0087,
        "text_style": "xmpp",
        "sip_style": "xmpp-first",
        "api": {"ordering": False, "docs": "https://jmp.chat",
                "note": "number management runs through cheogram's ad-hoc commands, there is no rest api to point at"},
        "inbound_texts": "as a jabber message to your jid, unlimited in and out including international, no webhook anywhere",
        "voicemail": "audio and a transcription, both delivered to jabber",
        "forwarding": "the jabber account is the address",
        "server": "xmpp first, a sip client also works",
        "works_while_off": {"texts": True, "voicemail": True, "live_calls": False},
        "verified": False,
        "note": "the most agent-shaped number here and the most expensive: five dollars a month buys unlimited texts and transcribed voicemail, but the inbox is a chat protocol, so the host has to run a jabber client instead of accepting a post.",
    },
    "voyced": {
        "provider": "voyced",
        "did_usd_month": 2.50,
        "text_style": "none",
        "sip_style": "registration",
        "api": {"ordering": False, "docs": "https://www.voyced.eu/clients/knowledgebase/620/Voyced-API-Access-What-does-this-mean.html",
                "note": "their own knowledgebase says the api is in active development and controlled testing, so ordering stays in their web store"},
        "inbound_texts": None,
        "voicemail": "their hosted voicemail on the number",
        "forwarding": "standard did routing, sip trunk or internal did",
        "server": "sip registration, plus internal dids and hosted pbx accounts",
        "works_while_off": {"texts": False, "voicemail": True, "live_calls": False},
        "verified": False,
        "note": "eu numbers and worldwide coverage, priced per country and billed per minute inbound, but nothing they publish claims sms on a geographic number: treat it as a voice number until a real text lands.",
    },
    "voxacall": {
        "provider": "voxacall",
        "did_usd_month": None,
        "text_style": "none",
        "sip_style": "trunk-route",
        "api": {"ordering": False, "docs": "https://voxacall.me",
                "note": "a developer api is advertised behind registration; no public spec to read, so nothing here is verified"},
        "inbound_texts": None,
        "voicemail": None,
        "forwarding": "trunk routing",
        "server": "sip trunk, no per number registration",
        "works_while_off": {"texts": False, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "no-kyc, crypto-paid trunking aimed at call centres: fast to open and the exact shape a recipient's risk engine blocks first, and no sms story at all. a voice option, not an inbox.",
    },
    "bitcall": {
        "provider": "bitcall",
        "did_usd_month": None,
        "text_style": "none",
        "sip_style": "registration",
        "api": {"ordering": False, "docs": "https://docs.bitcall.io",
                "note": "the api covers otp, esim and hlr; their own integration guides say inbound numbers are coming soon"},
        "inbound_texts": None,
        "voicemail": None,
        "forwarding": "outbound trunk only for now",
        "server": "outbound sip trunk with credentials",
        "works_while_off": {"texts": False, "voicemail": False, "live_calls": False},
        "verified": False,
        "note": "cheap international termination and a working api, but no inbound number yet, so it cannot be the inbox. worth revisiting when their dids ship.",
    },
}

OTP = {
    "sim": ("best", "a real mobile number with a radio behind it"),
    "companion-app": ("voice only", "an approving handset, not a code route"),
    "sms-capable-did": ("depends", "some senders refuse voip number types outright"),
    "sip-did": ("no", "a voice did is not a verification channel"),
}


def receives_texts(name):
    """the one question that decides whether a provider can be the inbox."""
    return bool(PROVIDERS[name].get("inbound_texts"))


def inbox_providers():
    return [n for n in PROVIDERS if receives_texts(n)]


def text_styles():
    return {name: entry["text_style"] for name, entry in PROVIDERS.items()}


def sip_styles():
    return {name: entry["sip_style"] for name, entry in PROVIDERS.items()}


def profile(name):
    key = name.lower().strip()
    if key not in PROVIDERS:
        raise KeyError(f"unknown provider: {name}")
    return PROVIDERS[key]


def works_while_off(name):
    return dict(profile(name)["works_while_off"])


def otp_viability(channel):
    verdict, why = OTP.get(channel, ("unknown", "not a channel we model"))
    return {"channel": channel, "viable": verdict, "why": why}


def still_voip(name):
    """the invariant that outlives every price: the number type does not change."""
    profile(name)
    return {"number_type": "voip", "markup_changes_trust": False,
            "refused_by": "a large share of signup and verification flows, banks nearly always"}
