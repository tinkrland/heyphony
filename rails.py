"""rails: the three platforms, as data, so the page and the code cannot drift while both are a contract.

nothing here joins a meeting yet. the dict exists so that the readme table, the signature notes and
whatever participant gets written later all read from one place, and so the tests can hold the prose to
it.

state values:

  contract   a shape with a join path and refusals, no participant, no meeting ever joined
  designed   the join path read from the platform's own documentation
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
        "state": "contract",
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
        "state": "contract",
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
        "gate": ["MEETING_BROWSER_PROFILE"],
        "state": "contract",
        "refused": ["a cold join", "an org whose tenant refuses outside guests"],
        "scope": "the platform most likely to refuse a guest mid-join, and the page says so rather "
                 "than blaming the participant later",
    },
}

STATES = ("contract", "designed", "verified")


def rail(name):
    return RAILS[name]


def gates():
    return {name: row["gate"] for name, row in RAILS.items()}


def by_state(state):
    return [name for name, row in RAILS.items() if row["state"] == state]


def table_rows():
    """the readme table, derived: name, join, signature presence, audio, state."""
    return [(row["name"], row["join"], "hs256 jwt" if row["signature"] else "none",
             row["audio"], row["state"]) for row in RAILS.values()]


def signature_of(name):
    """the jose fields for the one platform that has them, or None. nothing invents a signature."""
    return RAILS[name]["signature"]
