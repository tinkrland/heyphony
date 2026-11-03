"""signup: the four legs an account stands on, and where ours stop.

the owner's question is the right shape: an account elsewhere needs an address it can
verify, an inbox that answers while the machine sleeps, a browser somebody believes, and
sometimes a phone. we have three of those four, and the fourth is the interesting one.

nothing here creates an account. it says what a given service asks for, which leg is
closed today, and which part is a human's click by nature rather than by our laziness.
"""
import os

LEGS = {
    "address": {
        "have": "a custom domain on carlyemail, free (1000 messages + 3 inboxes/month); agentmail wants a paid plan for a domain",
        "state": "built",
        "note": "inbound works while the host is idle; sending is narrow (SMTP_URL) and gated",
    },
    "inbox": {
        "have": "the email lane's svix gate, and verification mail waiting after the fact",
        "state": "built",
        "note": "the lane that has to work while the machine is off, which is exactly a signup",
    },
    "browser": {
        "have": "the guest's own browser, on a fingerprinted machine with one geo, clock and locale",
        "state": "built",
        "note": ("better than a hosted browser for this: kernel-images gives you a chrome session, "
                 "we give you a machine whose ip, clock and font stack agree with each other. "
                 "captcha scores a reputation, not a user agent"),
    },
    "phone": {
        "have": "a voip did from voip.ms or flowroute, inbound-first",
        "state": "partial",
        "note": ("a voip number is refused by a large share of signup and verification flows "
                 "(see heyphony/src/providers.py). an app-only flow needs a real handset, and a "
                 "borrowed handset is still somebody else's identity, not yours"),
    },
}

# what each surface asks for, and what a cheaper path looks like. every verified flag is
# False because nobody has attempted one yet, and this file does not launder documentation
# into experience.
SERVICES = {
    "slack": {
        "wants": {"address": True, "inbox": True, "browser": True, "phone": False},
        "human_acts": ["accepting the terms as a person or org"],
        "cheaper_path": ("you rarely need slack's own account. the agent joins YOUR workspace by "
                         "invite, or as an app you install once, which is consent, not signup"),
        "verified": False,
        "evidence": "the email lane plus slack's own app install flow, both already in this branch",
    },
    "discord": {
        "wants": {"address": True, "inbox": True, "browser": True, "phone": "sometimes"},
        "human_acts": ["joining some servers asks for a verified number"],
        "cheaper_path": ("a bot token on your own server, which is what discord/ already uses for "
                         "watching and replying. an account is for reading as a person, not for work"),
        "verified": False,
        "evidence": "discord/ lane watches with a bot token; no person-account path has been tried",
    },
    "github": {
        "wants": {"address": True, "inbox": True, "browser": True, "phone": False},
        "human_acts": [],
        "cheaper_path": "an org invite or a fine-grained token beats a new identity here too",
        "verified": False,
        "evidence": "no attempt; listed because it is the flow most likely to be asked for next",
    },
    "google": {
        "wants": {"address": True, "inbox": True, "browser": True, "phone": "sometimes"},
        "human_acts": ["device attestation and a number for many paths"],
        "cheaper_path": "an account a person already holds, reached as a session, not a new signup",
        "refused": ("signup leans on play integrity / device check and a number we cannot own, so a "
                    "guest that fakes it is committing the exact tell the fingerprint layer exists "
                    "to avoid. use an account a human already holds"),
        "verified": False,
        "evidence": "refused by design, not by a failed attempt",
    },
}

# things this module will not do however the plan is written
REFUSED = {
    "autonomous-signup-against-terms": "creating accounts by automation where a platform forbids it is a banned pattern, not a growth hack",
    "signup-to-evade": "a new account after a ban or a suspension is the same person wearing a second face",
    "number-type-fiction": "a voip did presented as a mobile number is a lie a carrier notices",
    "borrowed-identity": "a device somebody else owns is their sim and their account; that is borrowing, not owning",
}


def plan(service, env=None):
    """the four legs for one service, with what stops it today. deterministic, no io."""
    env = env if env is not None else os.environ
    key = str(service).strip().lower()
    if key not in SERVICES:
        return {"service": key, "known": False,
                "known_services": sorted(SERVICES),
                "refused": REFUSED["autonomous-signup-against-terms"]}
    spec = SERVICES[key]
    legs = {}
    for leg, want in spec["wants"].items():
        state = LEGS[leg]
        legs[leg] = {"wanted": want, "we_have": state["have"], "state": state["state"]}
    legs["inbox"]["open"] = bool(env.get("CARLYEMAIL_SIGNING_SECRET") or env.get("HEYPHONY_MAIL_SECRET"))
    phone_wanted = spec["wants"].get("phone") not in (False, None)
    legs["phone"]["viable"] = not phone_wanted
    legs["phone"]["why"] = ("a voip class number, refused by many of these flows"
                           if phone_wanted else "not asked for")
    stops = []
    if spec.get("refused"):
        stops.append(spec["refused"])
    if phone_wanted:
        stops.append("a number may be demanded, and ours is voip class; that is where it ends")
    if not legs["inbox"]["open"]:
        stops.append("the inbox gate is unset, so nothing could be verified anyway")
    return {
        "service": key,
        "known": True,
        "legs": legs,
        "cheaper_path": spec["cheaper_path"],
        "human_acts": spec["human_acts"],
        "stops": stops,
        "verified": spec["verified"],
        "evidence": spec["evidence"],
        "rule": ("an account is state, not a secret: whatever creates one has to live on the "
                 "identity that will use it, or it strands a login the way a session does"),
        "refused": REFUSED,
    }


def listing():
    """one line per service, for `comms signup --list`."""
    return [{"service": k, "wants": sorted(v["wants"]), "cheaper_path": v["cheaper_path"],
             "verified": v["verified"]} for k, v in sorted(SERVICES.items())]


def device_note():
    """the owner asked whether we used phone-harness. we read it; here is the useful half."""
    return {
        "used": False,
        "what_it_is": ("shawnpana/phone-harness, mit: four helpers over a phone (open_app, tap_text, "
                       "type_text, screen), iphones through macOS mirroring + vision ocr, androids over adb"),
        "why_not_for_signup": ("a phone we do not own is somebody else's sim and somebody else's account, "
                               "useful for app-only flows where no web path exists and useless as an "
                               "identity we hold"),
        "where_it_would_fit": ("a lane that must touch an ios-only onboarding screen on a handset we hold, "
                               "behind the same rule as every other device: it may act, it may not "
                               "become the identity"),
    }
