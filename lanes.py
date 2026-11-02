"""lanes: the carriers this branch intends to speak, as data rather than prose.

nothing here catches anything yet. the dict exists so the readme, the registry and the tests can be
wrong about the same thing at the same time, which is the only way a page like this stays honest while
it is a contract rather than a stack.

state values, and what each one commits to:

  contract   a shape with a gate and a scope, no catcher and no message ever received
  designed   a gate and a payload shape read from the carrier's own documentation
  verified   one real message arrived and was stored

every row starts at contract. a row moves to designed when the payload shape has been read from source,
and to verified only when something arrives that nobody typed by hand.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

LANES = {
    "mail": {
        "name": "mail",
        "carrier": "agentmail, carlyemail",
        "intake": "svix signed webhook, or a plain header when the sender has no svix",
        "gate": ["MAIL_WEBHOOK_SECRET"],
        "state": "contract",
        "refused": ["attachments that are executables", "sending as somebody else"],
        "scope": "the lane that works while the machine is off, which is why it is a signup lane as "
                 "well as a conversation one",
    },
    "imessage": {
        "name": "imessage",
        "carrier": "photon spectrum",
        "intake": "v0 signed webhook, verified against the raw body",
        "gate": ["IMESSAGE_WEBHOOK_SECRET"],
        "state": "contract",
        "refused": ["an apple bridge of our own", "registering a voip did as an apple id"],
        "scope": "deliberately thin: the free tier pointed at whitelisted people, with sms underneath "
                 "as the floor",
    },
    "whatsapp": {
        "name": "whatsapp",
        "carrier": "waha",
        "intake": "hmac webhook, sha256 or sha512, digits whitelist",
        "gate": ["WHATSAPP_WEBHOOK_SECRET"],
        "state": "contract",
        "refused": ["group replies", "anyone not on the whitelist"],
        "scope": "one number, one handset-shaped session, and a whitelist that defaults to nobody",
    },
    "signal": {
        "name": "signal",
        "carrier": "signal-cli, linked device or registered number",
        "intake": "a local cli polled on a schedule, no webhook exists",
        "gate": ["HEYPHONY_SIP_DID"],
        "state": "contract",
        "refused": ["a bot api, because signal has none"],
        "scope": "the rail a number unlocks first, because signal will take a number that other "
                 "services refuse",
    },
    "telegram": {
        "name": "telegram",
        "carrier": "bot api, or a user account",
        "intake": "webhook with a secret token header, compared in constant time",
        "gate": ["TELEGRAM_BOT_TOKEN"],
        "state": "contract",
        "refused": ["group scraping", "an api id used to drive somebody else's account"],
        "scope": "two paths wearing one name: a bot is a thing you own, an account is a person",
    },
    "slack": {
        "name": "slack",
        "carrier": "events api",
        "intake": "url verification answered first, then signed events",
        "gate": ["SLACK_SIGNING_SECRET"],
        "state": "contract",
        "refused": ["workspace scraping", "replying in a channel that has not addressed the agent"],
        "scope": "the work rail, which means a whitelist that is a workspace and a channel rather "
                 "than a phone number",
    },
    "discord": {
        "name": "discord",
        "carrier": "gateway",
        "intake": "one long lived socket, read only",
        "gate": ["DISCORD_BOT_TOKEN"],
        "state": "contract",
        "refused": ["replying in a room", "posting unprompted"],
        "scope": "a monitoring lane without a mouth, which is the only shape worth offering here",
    },
}

STATES = ("contract", "designed", "verified")


def lane(name):
    return LANES[name]


def gates():
    """every env var a lane would need, so a deployment can be checked before a lane is opened."""
    return {name: row["gate"] for name, row in LANES.items()}


def state_of(name):
    return LANES[name]["state"]


def by_state(state):
    return [name for name, row in LANES.items() if row["state"] == state]


def table_rows():
    """the readme table, derived, so the page cannot claim a lane the data does not have."""
    return [(row["name"], row["carrier"], row["intake"], row["gate"][0], row["state"])
            for row in LANES.values()]
