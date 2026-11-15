"""rails: the three platforms, as data, so the page and the code cannot drift while both are a contract.

nothing here joins a meeting yet. the dict exists so that the readme table, the signature notes and
whatever participant gets written later all read from one place, and so the tests can hold the prose to
it.

state values:

  designed   the join path read from the platform's own documentation and implemented here: the
             signature is minted and checked, the plan is built, and no meeting has been joined
  verified   a real meeting joined, with the human who invited the agent saying it worked
  verified   a real meeting joined, with the human who invited the agent saying it worked
"""

RAILS = {
    "zoom": {
        "name": "zoom",
        "join": "meeting sdk join token, or the browser client with a link",
        "signature": {
            "alg": "HS256",
            "message": "base64url(header) + '.' + base64url(payload)",
            "payload": {"sdkKey": "the meeting sdk key", "mn": "the meeting number",
                        "role": 0, "iat": "now minus 30 seconds", "exp": "now plus two hours",
                        "tokenExp": "now plus two hours"},
            "token": "base64url(signature + '.' + message + '.' + random hex)",
            "why_backdated": "iat is now minus 30 seconds, because a clock half a minute fast is a "
                             "token that is not yet valid, and that presents as a 401 rather than as a "
                             "clock problem",
        },
        "audio": "livekit room",
        "screenshare": "getDisplayMedia, a human picks the surface",
        "gate": ["ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"],
        "signal": "raise hand, reactions and the screen share, all through the room's own ui",
        "evidence": "the join token is minted and re-verified in tests/selftest.py; no meeting joined",
        "state": "built",
        "refused": ["a cold join from a meeting id", "recording without the host's consent"],
        "scope": "the one platform with a documented programmatic join, so the one where a wrong "
                 "field is a silent failure",
    },
    "googlemeet": {
        "name": "googlemeet",
        "join": "a browser participant, because there is no bot api",
        "signature": None,
        "audio": "livekit room",
        "screenshare": "getDisplayMedia, a human picks the surface",
        "gate": ["MEETING_BROWSER_PROFILE"],
        "signal": "browser ui only: there is no host api to raise a hand through",
        "evidence": "the browser room is the whole join path; no browser has been sent to one",
        "state": "built",
        "refused": ["a cold join", "a profile that is not signed in", "recording by default"],
        "scope": "the invite is the permission, and the participant is a headless browser wearing a "
                 "normal participant's clothes",
    },
    "teams": {
        "name": "teams",
        "join": "a browser participant, tenant policy permitting",
        "signature": None,
        "audio": "livekit room",
        "screenshare": "getDisplayMedia, a human picks the surface",
        "gate": ["MEETING_BROWSER_PROFILE", "MS_TENANT_ID"],
        "signal": "browser ui only, and a tenant policy can end the join before any ui appears",
        "evidence": "the tenant gate is named in the plan; no tenant has been asked for one",
        "state": "built",
        "refused": ["a cold join", "an org whose tenant refuses outside guests"],
        "scope": "the platform most likely to refuse a guest mid-join, and the page says so rather "
                 "than blaming the participant later",
    },
}

# `built` is the rung the page was missing. the join path is implemented and the suite drives it,
# and no room has been joined, so calling every row `designed` read as "not set up yet" to anybody
# who did not write the vocabulary. designed stays for a shape read from docs and exercised nowhere.
STATES = ("designed", "built", "verified")

MEANS = {
    "designed": "the join path is read from the platform's own documentation and nothing here drives it",
    "built": "the join path is here and this branch's suite drives it; no room has been joined",
    "verified": "a room was joined with the person who sent the invite saying it worked",
}


def rail(name):
    return RAILS[name]


def gates():
    return {name: row["gate"] for name, row in RAILS.items()}


def checked(rows=None):
    """every row's rung has to be one of STATES: a made-up word is a typo that looks like progress."""
    for row in (rows or RAILS).values():
        if row.get("state") not in STATES:
            raise ValueError(f"{row.get('name')} claims {row.get('state')!r}; the rungs are {', '.join(STATES)}")
    return rows or RAILS


def by_state(state):
    return [name for name, row in RAILS.items() if row["state"] == state]


def table_rows():
    """the readme table, derived: name, join, signature presence, audio, state."""
    return [(row["name"], row["join"], "hs256 jwt" if row["signature"] else "none",
             row["audio"], row["state"]) for row in RAILS.values()]


def platform_names():
    """the keys a `bin/meetings join --platform` will accept, so the shim cannot invent one."""
    return sorted(RAILS)


def signature_of(name):
    """the jose fields for the one platform that has them, or None. nothing invents a signature."""
    return RAILS[name]["signature"]
