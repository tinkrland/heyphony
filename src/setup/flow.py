"""the guided setup, in two shapes at once: a menu for a person, flags for a process.

`heyphony setup select sip` walks three small choices - provider, then whether the did already
exists or has to be ordered, then the number itself - and prints the exact connect command with
the parts a human still has to fetch from the dashboard marked.

the same module answers to flags, because the caller is often not a person: every menu is also a
key in the data, and a non-tty run with missing answers returns the next question as json instead
of blocking on a prompt. that is what makes setup operatable by an agent, not just readable by one.
"""
import sys

from src import providers
from src.setup import routes

RAILS = {
    "sip": {
        "rail": "sip",
        "label": "sip",
        "detail": "a did from a provider that sells them for about a dollar a month",
        "gate": "HEYPHONY_SIP_DID",
    },
}

PROVIDER_CHOICES = [
    {"key": "voip.ms", "label": "voip.ms", "group": "texts reach an inbox",
     "detail": "a dollar a month, carrier voicemail and texts land in email, so the inbox keeps working with the machine off"},
    {"key": "flowroute", "label": "flowroute", "group": "texts reach an inbox",
     "detail": "a dollar a month, texts by webhook or smpp, no voicemail fallback at the carrier"},
    {"key": "anveo", "label": "anveo", "group": "texts reach an inbox",
     "detail": "99 cents, texts forwarded to a url with placeholders, call flow voicemail, sms on us/ca/uk numbers"},
    {"key": "signalwire", "label": "signalwire", "group": "texts reach an inbox",
     "detail": "50 cents, a swml message handler posts json, sip credentials you choose, ordering over an api"},
    {"key": "questblue", "label": "questblue", "group": "texts reach an inbox",
     "detail": "70 cents, a trunk provider: the number routes at your trunk and sms posts to a url you set over their api"},
    {"key": "bulkvs", "label": "bulkvs", "group": "texts reach an inbox",
     "detail": "six cents a month wholesale, one webhook in the api and a webhook field per number, US and Canada numbers"},
    {"key": "jmp.chat", "label": "jmp.chat", "group": "texts reach an inbox",
     "detail": "4.99, unlimited texts and transcribed voicemail, arriving as jabber messages instead of a webhook"},
    {"key": "voyced", "label": "voyced", "group": "voice only, no inbox",
     "detail": "EU and worldwide numbers from about 2.50, per-minute inbound, but no sms claim and an api still in testing"},
    {"key": "voxacall", "label": "voxacall", "group": "voice only, no inbox",
     "detail": "no-kyc crypto-paid trunking, fast to open, no public sms story and the shape risk engines block first"},
    {"key": "bitcall", "label": "bitcall", "group": "voice only, no inbox",
     "detail": "cheap international termination and a real api, but inbound numbers are on their roadmap, so it cannot be the inbox"},
]
DID_CHOICES = [
    {"key": "existing", "label": "i already have a sip did",
     "detail": "paste the number, then the sip username and password from the provider dashboard"},
    {"key": "new", "label": "get a new one",
     "detail": "opens the provider portal in a browser; programmatic ordering comes later, by cli"},
]

PORTALS = {
    "voip.ms": "https://voip.ms",
    "flowroute": "https://manage.flowroute.com",
    "anveo": "https://www.anveo.com",
    "signalwire": "https://signalwire.com",
    "questblue": "https://customer.questblue.com",
}


def _tty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _readline(stream_in, stream_out, prompt):
    stream_out.write(prompt)
    stream_out.flush()
    line = stream_in.readline()
    return (line or "").strip()


def select(title, choices, default=0, stream_in=None, stream_out=None, tty=None):
    """a menu when someone is watching, a number when they are not, a key either way.

    arrow keys and enter when the stream is a terminal; a typed number otherwise. both paths
    return the same key, so the flow below never has to know which kind of caller it has.
    """
    stream_in = stream_in or sys.stdin
    stream_out = stream_out or sys.stdout
    interactive = _tty(stream_in) and _tty(stream_out) if tty is None else tty
    keys = [c["key"] for c in choices]

    if not interactive:
        while True:
            answer = _readline(stream_in, stream_out, f"{title} [{default + 1}]: ")
            if not answer:
                return keys[default]
            if answer.isdigit() and 1 <= int(answer) <= len(choices):
                return keys[int(answer) - 1]
            if answer in keys:
                return answer
            stream_out.write(f"not one of: {', '.join(keys)}\n")

    try:
        import termios
        import tty as ttymod
        fd = stream_in.fileno()
        saved = termios.tcgetattr(fd)
    except Exception:
        saved, fd = None, None

    index = default
    if saved is not None:
        try:
            ttymod.setcbreak(fd)
            while True:
                stream_out.write(f"\n{title}\n")
                for i, choice in enumerate(choices):
                    mark = ">" if i == index else " "
                    stream_out.write(f" {mark} {choice['label']}\n")
                    if i == index:
                        stream_out.write(f"     {choice['detail']}\n")
                stream_out.write("   up/down to move, enter to pick\n")
                stream_out.flush()
                char = stream_in.read(1)
                if char == "":  # stdin closed under us: take the highlighted row, never hang
                    stream_out.write("\n")
                    return keys[index]
                if char in ("\r", "\n"):
                    stream_out.write("\n")
                    return keys[index]
                if char == "j":
                    index = min(index + 1, len(choices) - 1)
                elif char == "k":
                    index = max(index - 1, 0)
                elif char == "\x1b":  # an escape sequence: arrow keys
                    rest = stream_in.read(2)
                    if rest == "[B":
                        index = min(index + 1, len(choices) - 1)
                    elif rest == "[A":
                        index = max(index - 1, 0)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    # a terminal we cannot put in cbreak mode still gets a menu, just a typed one
    stream_out.write(f"\n{title}\n")
    for i, choice in enumerate(choices):
        stream_out.write(f"  {i + 1}. {choice['label']} - {choice['detail']}\n")
    return select(title, choices, default, stream_in, stream_out, tty=False)


def ask(prompt, stream_in=None, stream_out=None):
    """one free text answer. the did is the only thing here a menu cannot offer."""
    stream_in = stream_in or sys.stdin
    stream_out = stream_out or sys.stdout
    return _readline(stream_in, stream_out, prompt)


def valid_did(value):
    """e164, loosely: a plus and digits. a number we cannot dial is worse than no number."""
    text = str(value or "").strip()
    return text.startswith("+") and text[1:].isdigit() and 7 <= len(text[1:]) <= 15


def plan_sip(provider, did=None, new=False):
    """one dict that is the whole flow's result, whatever answered the questions."""
    key = str(provider or "").lower().replace("voipms", "voip.ms").strip()
    if key not in providers.PROVIDERS:
        raise ValueError(f"unknown provider: {provider}")
    profile = providers.profile(key)
    steps = []
    browser = None
    source = "existing"

    if new:
        source = "new"
        browser = {"url": PORTALS[key], "deep_link_verified": False,
                   "why": f"sign in, order a number ({profile['did_usd_month']:.2f} usd a month), and confirm sms is enabled on it",
                   "note": "the portal root on purpose: a guessed deep link rots and lands somebody on a 404"}
        steps.append("order a did in the browser above, and check that the number is sms capable before paying")
    else:
        steps.append("confirm the did is sms capable; an inbound inbox is not a verification route")

    if profile.get("sip_style") == "trunk-route":
        steps.append("create the sip trunk first, then point this number at it (route2trunk in the portal "
                     "or `PUT /did`): the credentials belong to the trunk, not to the number")
    hook = routes.hook(key, did=None if new else did)
    steps += [
        "fetch the sip username and password for that number from the provider dashboard",
        "run the connect command below on the host, not in a burnable guest",
        "arm the text hook below, or the provider's carrier side email forwarding, so texts have a home",
        "point voicemail at a folder the views can read, or accept that this provider has no fallback",
        "start the host client, then `heyphony calls` after one real call",
        "open `heyphony app` and read the caught messages and voicemail as one thread per person",
    ]
    connect = (f"heyphony connect sip --provider {key} --did {did or '+1...'}"
               " --username <sip username> --password <sip password>")
    return {
        "rail": "sip",
        "provider": key,
        "provider_choices": [c["key"] for c in PROVIDER_CHOICES],
        "did": {"source": source, "number": None if new else did,
                "sms_capable": "confirm at the provider before relying on texts"},
        "browser": browser,
        "steps": steps,
        "connect": connect,
        "from_owner": ["the did", "the sip username", "the sip password"],
        "proves": "one inbound text in `heyphony open messages` (or in `heyphony app`), one voicemail "
                  "in the voicemail tab, and one call in `heyphony calls`",
        "catching": {"kind": hook["kind"], "paste_url": hook.get("paste_url"),
                     "serve": "heyphony serve --port 8099 --token <token>",
                     "arm": hook["cli"],
                     "where_texts_land": ("the catcher, then ~/.local/share/telephony/inbox.jsonl"
                                          if hook["kind"] != "email" else
                                          "email on this provider, so the email lane is their home"),
                     "why": "texts never travel over sip: what makes them reliable is that a provider holds "
                            "them and posts or emails them, so the inbox works with the machine asleep"},
        "voicemail": {"where": ("the carrier answers and emails the recording (voip.ms), or call flow "
                                "voicemail (anveo)" if profile["works_while_off"]["voicemail"] else
                                "no carrier fallback: a caller who reaches nothing gets nothing"),
                      "land": "HEYPHONY_VOICEMAIL_DIR, default ~/.local/share/telephony/voicemail, "
                              "audio plus a <name>.json sidecar for sender, seconds and transcript",
                      "read": "heyphony open voicemail  |  heyphony app (voicemail tab)",
                      "why": "voicemail is a carrier feature, so it exists when the provider has one and "
                             "not otherwise; a missing sidecar means no transcript rather than an invented one"},
        "launcher": {"command": "heyphony app --port 8790",
                     "tabs": ["caught messages", "voicemail", "calls"],
                     "reply": "drafts in the thread and shows the route; it never sends on your behalf"},
        "provisioning": ({"now": "cli", "browser": browser,
                          "command": f"heyphony setup provision --provider anveo --area-code <n> "
                                     f"--sms-url {routes.paste_url('anveo')} --apply",
                          "why": "anveo publishes areas, order and sms url as three api actions, so the same cli "
                                 "can buy the number and point its texts at the catcher without a browser",
                          "lookup": "heyphony setup areas --area-code <n>  (stock and price per rate plan, "
                                    "so the area is a choice rather than a guess)",
                          "stops_before": "DID.ORDER", "spends_money": False,
                          "why_money_wait": "area stock and prices are free to ask for, an order bills the "
                                            "account, and no payment rail is wired here on purpose",
                          "test_flag": "anveo's TEST parameter sandboxes the request"}
                         if key == "anveo" else
                         {"now": "browser", "later": "programmatic ordering from the cli",
                          "why": "ordering a number is a purchase, and a purchase is a person's act until the "
                                 "provider documents enough to script it. anveo does, the rest do not yet"}),
        "works_while_off": profile["works_while_off"],
        "sip_style": profile.get("sip_style"),
        "pricing": {"did_usd_month": profile["did_usd_month"],
                    "inbound_texts": profile["inbound_texts"],
                    "inbound_text_usd": profile.get("inbound_text_usd"),
                    "note": profile["note"]},
        "text_hook": hook,
        "number_type": "voip",
        "verified": False,
        "evidence": "the flow is tested against stored answers; no did has been ordered through it",
    }


def needs(question, choices):
    return {"ok": False, "needs": question, "flag": f"--{question}",
            "options": [{"key": c["key"], "detail": c["detail"]} for c in choices],
            "how": "answer with the flag, or run it on a terminal to pick from the menu"}


def render(plan):
    """the human shape of the same dict: short lines, no braces."""
    lines = [f"rail: {plan['rail']}  provider: {plan['provider']}",
             f"did: {plan['did']['number'] or 'to order'}", ""]
    if plan["browser"]:
        lines += [f"order one here: {plan['browser']['url']}",
                  f"  {plan['browser']['why']}", ""]
    lines += ["what happens next:"]
    lines += [f"  {i}. {step}" for i, step in enumerate(plan["steps"], 1)]
    hook = plan.get("text_hook") or {}
    if hook.get("paste_url"):
        lines += ["", f"texts land here: {hook['paste_url']}  ({hook['kind']})"]
        lines += [f"  wire it with: {hook['cli']}"]
    elif hook.get("kind") == "email":
        lines += ["", "texts arrive by email on this provider, so the email lane is their home, not the catcher"]
    elif hook.get("kind") == "xmpp":
        lines += ["", "texts arrive as jabber messages: a client on the host is the receiver, so there is no url to paste"]
    elif hook.get("kind") == "none":
        lines += ["", "this number cannot receive a text yet, so it is a voice number and not an inbox"]
    lines += ["", f"then: {plan['connect']}", "",
              f"proves it: {plan['proves']}",
              "state: designed. this becomes real when one live call or text carries."]
    return "\n".join(lines)
