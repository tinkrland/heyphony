"""forwarding: sending a call or a message somewhere other than the endpoint that owns the number.

two ideas share this file because they share a question ("who receives when the number is reached, and
when it is not me?") and because the honest answer is different for each. a call can be forwarded by
the carrier, the endpoint, or a handler, and the three fail differently. a text cannot really be
forwarded at all: either the carrier re-addresses it before we ever see it, or we receive it and send a
second message, which is a re-send wearing forwarding's clothes.

nothing here calls a carrier. it says what each mode means, where it can be set, whether it survives
the host being down, and what would have to be true before it was wired. every capability is
`verified: False`, because nobody has set one yet, and this file does not launder documentation into
experience.
"""
import re

from src.providers import PROVIDERS

# a call can be handed off at five moments, and the moments are the standard ones every pbx has had
# since the 1980s. the names are the ones a carrier's dashboard will use.
CALL_MODES = {
    "unconditional": {
        "aka": "cfu, forward always",
        "when": "every call, before the endpoint rings",
        "where": "carrier, or the endpoint as a 302 before answering",
        "survives_host_down": True,
        "catch": ("the number stops being yours to answer. this is a redirect, not a filter, so an "
                  "agent behind it receives nothing and cannot decide per caller"),
    },
    "busy": {
        "aka": "cfb, forward on busy",
        "when": "when the endpoint answers 486 busy",
        "where": "carrier, or the endpoint",
        "survives_host_down": False,
        "catch": ("needs a registered endpoint that can say busy. a sleeping host is not busy, it is "
                  "unreachable, which is a different mode and a common configuration mistake"),
    },
    "no_answer": {
        "aka": "cfnry, forward on no reply",
        "when": "after the carrier's ring timer expires, usually 15 to 30 seconds",
        "where": "carrier, or the endpoint",
        "survives_host_down": False,
        "catch": ("the timer is the whole feature and it is a personality decision: shorter than the "
                  "agent's answer time and every call is forwarded, longer and the caller has been "
                  "listening to nothing for half a minute"),
    },
    "not_reachable": {
        "aka": "cfnrc, forward when unreachable",
        "when": "when the endpoint is unregistered, or the host is asleep",
        "where": "carrier",
        "survives_host_down": True,
        "catch": ("the interesting one here, because a number on a host that sleeps is unreachable most "
                  "of the day. it is also the mode most often mistaken for a general safety net: it only "
                  "fires when registration has already dropped, not when the host is up and wedged"),
    },
    "selective": {
        "aka": "cfs, forward from particular numbers",
        "when": "when the caller matches a rule: an exact number, a prefix, or a list",
        "where": "a handler we write, or a carrier that sells caller based routing",
        "survives_host_down": False,
        "catch": ("not a sip primitive and not standard across carriers. where it exists it is a "
                  "dashboard feature or a branch in a call handler, so it costs a second leg and the "
                  "host has to be awake to make the decision. the honest default is to implement it in "
                  "the handler and stop assuming the number can do it alone"),
    },
}

# a text has no equivalent ladder. the two real shapes are the carrier re-addressing it, or us
# receiving it and sending another one, and the second is a different product than it sounds.
MESSAGE_MODES = {
    "carrier_relay": {
        "aka": "the carrier re-addresses the text",
        "when": "before it ever reaches us: per number the carrier sends it to an email or an xmpp jid",
        "where": "carrier",
        "survives_host_down": True,
        "catch": ("the sender's thread and the recipient's thread are not the same thread. whoever reads "
                  "the relayed copy is reading mail, and replying from that copy reaches nobody unless "
                  "the carrier accepts replies back into the number"),
    },
    "webhook_relay": {
        "aka": "we receive it and send a second text",
        "when": "after the carrier posts the inbound message to our catcher",
        "where": "our host, on the way out of the inbox",
        "survives_host_down": False,
        "catch": ("this is a re-send, not a forward. the recipient sees a message from THIS number, the "
                  "original sender sees silence, and the two hops are two messages with two costs. call "
                  "it relaying and the surprise goes away"),
    },
    "email_fallback": {
        "aka": "text arrives as mail while the host sleeps",
        "when": "always, because the carrier does it without us",
        "where": "carrier",
        "survives_host_down": True,
        "catch": ("one way, and ugly for a conversation. it is the thing that makes an inbox survive the "
                  "machine being off, which is already how this repo's inbound texts work"),
    },
    "store_and_relay": {
        "aka": "hold it, then deliver when the host wakes",
        "when": "after the fact, on our own schedule",
        "where": "our host",
        "survives_host_down": True,
        "catch": ("late by however long the host slept. fine for a digest, wrong for an answer that was "
                  "expected in a minute"),
    },
}

TARGETS = {
    "pstn": {"what": "another did, on any carrier", "needs": "a forward to an e164, which every carrier sells",
             "cost": "a second leg on the call, a second message on a text"},
    "sip_uri": {"what": "a sip address, which may never touch the pstn",
                "needs": "the carrier must accept a uri target; several only accept another did",
                "cost": "one leg, if the target is on the same carrier or a peered one"},
    "voicemail": {"what": "a mailbox, the carrier's or ours", "needs": "nothing beyond the number",
                  "cost": "none, and it is the target that survives everything"},
    "email": {"what": "a mailbox, for texts and for voicemail as a file", "needs": "a carrier that does sms-to-email",
              "cost": "none at the carrier, a mail account at the far end"},
    "lane": {"what": "the agent itself, as the endpoint", "needs": "a registered endpoint and a host that is awake",
             "cost": "the normal path, no forward at all"},
    "webhook": {"what": "an http endpoint we control", "needs": "a carrier that posts inbound texts to a url",
                "cost": "our own handler, and a host awake to answer it"},
}

MATCH_KINDS = ("any", "exact", "prefix", "list")

# a forward that points somewhere expensive is the oldest fraud in the book: international revenue
# share fraud sends traffic to a number whose owner is paid for the minutes, and the person paying is
# whoever owns the number being forwarded. the list is a guardrail, not an audit.
PREMIUM_PREFIXES = ("+1900",)

REFUSED = {
    "forwarding-as-a-campaign": ("pointing a number at a list is bulk outbound with an extra step. this "
                                 "repo refuses the campaign, so it refuses the forward that is one"),
    "premium-or-irsr-target": ("forwarding to a premium rate or revenue share number is the fraud carriers "
                               "police hardest, and being the one who configured it does not read as a "
                               "mistake afterwards"),
    "somebody-elses-number": ("you can forward what you hold. a target you do not own is a reroute of "
                              "traffic that is not yours"),
    "forward-pretending-to-be-the-original": ("passing the original caller id through a forward while the "
                                              "call is answered somewhere else is a presentation choice made "
                                              "for the callee, not us"),
    "silent-forward": ("a caller who reaches a different endpoint than the number they dialled should find "
                       "out from the greeting, not from a surprise"),
}

E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def call_plan(mode, target="pstn"):
    """what one call mode means, where it is set, and what it costs. deterministic, no io."""
    if mode not in CALL_MODES:
        return {"mode": mode, "known": False, "known_modes": sorted(CALL_MODES)}
    if target not in TARGETS:
        return {"mode": mode, "known": True, "target": target, "target_known": False,
                "known_targets": sorted(TARGETS)}
    spec = CALL_MODES[mode]
    return {
        "mode": mode, "known": True, "target": target,
        "aka": spec["aka"], "when": spec["when"], "where": spec["where"],
        "survives_host_down": spec["survives_host_down"],
        "target_needs": TARGETS[target]["needs"], "cost": TARGETS[target]["cost"],
        "catch": spec["catch"],
        "verified": False,
        "evidence": "read from the standard call forwarding names and each carrier's own routing page, "
                    "not exercised against a number",
    }


def message_plan(mode, target="pstn"):
    """the same question for a text, where the answer is not a ladder of five modes."""
    if mode not in MESSAGE_MODES:
        return {"mode": mode, "known": False, "known_modes": sorted(MESSAGE_MODES)}
    if target not in TARGETS:
        return {"mode": mode, "known": True, "target": target, "target_known": False,
                "known_targets": sorted(TARGETS)}
    spec = MESSAGE_MODES[mode]
    honest = spec["catch"]
    if mode == "carrier_relay" and target not in ("email", "lane"):
        honest += f". a carrier relay to {target} is not a thing: carriers relay texts to addresses, not to numbers"
    return {
        "mode": mode, "known": True, "target": target,
        "aka": spec["aka"], "when": spec["when"], "where": spec["where"],
        "survives_host_down": spec["survives_host_down"],
        "target_needs": TARGETS[target]["needs"], "cost": TARGETS[target]["cost"],
        "catch": honest, "verified": False,
        "evidence": "read from each carrier's own inbound text documentation, not exercised",
    }


def _call_class(forwarding):
    """what a provider's own forwarding sentence says it can be asked for. derived, never invented."""
    text = (forwarding or "").lower()
    if "not relied" in text or "outbound trunk only" in text:
        return "none-claimed"
    if "conditional" in text:
        return "carrier-conditional"
    if "call flow" in text:
        return "dashboard-flow"
    if "decides" in text:
        return "handler"
    if "failover" in text:
        return "number-record"
    if "jabber" in text or "xmpp" in text:
        return "xmpp-address"
    if "trunk" in text or "did routing" in text:
        return "did-routing"
    return "unclassified"


def _message_class(provider):
    """where a carrier can put an inbound text: an address it relays to, a url it posts to, or nowhere."""
    inbound = (provider.get("inbound_texts") or "").lower()
    style = (provider.get("text_style") or "").lower()
    relays = [address for address, needle in (("email", "email"), ("xmpp", "xmpp"),
                                              ("3cx", "3cx"), ("yeastar", "yeastar"))
              if needle in inbound]
    posts = style in ("webhook-json", "url-forward", "post-to-url")
    if not relays and not posts:
        return "none-claimed"
    if relays and posts:
        return "both"
    return "carrier-relay" if relays else "webhook"


class ProviderView(dict):
    """a plain dict with the provider's name in it, so json out of a plan reads like the rest of the repo."""


def provider_view(name):
    """what this provider can be asked for, in its own words plus our classification."""
    provider = PROVIDERS.get(name)
    if provider is None:
        return {"provider": name, "known": False, "known_providers": sorted(PROVIDERS)}
    call = _call_class(provider.get("forwarding"))
    message = _message_class(provider)
    needs = {
        "carrier-conditional": "the carrier's own conditional forwarding, set per number",
        "dashboard-flow": "a call flow built in the carrier's dashboard, which is a click path not an api",
        "handler": "a handler we write, so the decision costs a leg and needs the host awake",
        "number-record": "a field on the number record, set by the carrier",
        "xmpp-address": "the jabber address is the destination, so forwarding is an account question",
        "did-routing": "the did's own routing target, which is usually another did or a trunk",
        "none-claimed": "nothing this repo will claim for it",
        "unclassified": "reading its page before saying anything",
    }
    return ProviderView({
        "provider": name, "known": True,
        "call": call, "call_needs": needs.get(call, "reading its page"),
        "message": message,
        "message_relays_to": sorted({a for a in ("email", "xmpp", "3cx", "yeastar")
                                     if a in (provider.get("inbound_texts") or "").lower()}),
        "their_words": {"forwarding": provider.get("forwarding"),
                        "inbound_texts": provider.get("inbound_texts")},
        "survives_host_down": provider.get("works_while_off"),
        "verified": False,
    })


def providers_view():
    """every provider, so a plan cannot quietly skip one when the list grows."""
    return [provider_view(name) for name in sorted(PROVIDERS)]


def rule(match="any", values=(), call=None, message=None, window=None):
    """the shape of one rule, normalized so a plan can be compared rather than eyeballed."""
    if match == "exact" or match == "prefix":
        values = [values] if isinstance(values, str) else list(values)
    elif match == "any":
        values = []
    elif match == "list":
        values = list(values)
    return {"match": match, "values": values, "call": call, "message": message, "window": window}


def rule_problem(rule_, own_dids=()):
    """everything wrong with one rule, as a list, because a rule with two problems has two."""
    problems = []
    if not isinstance(rule_, dict):
        return ["a rule is a dict"]
    match = rule_.get("match")
    if match not in MATCH_KINDS:
        problems.append(f"match kind {match!r} is not one of {', '.join(MATCH_KINDS)}")
    values = rule_.get("values") or []
    if match in ("exact", "prefix") and len(values) != 1:
        problems.append(f"{match} takes exactly one value, got {len(values)}")
    if match == "list" and not values:
        problems.append("a list match with no values matches nobody, which is a rule that does nothing")
    for value in values:
        if match == "exact" and not E164.match(str(value)):
            problems.append(f"{value!r} is not an e164, so an exact match on it will never fire")
        if match == "prefix" and not str(value).startswith("+") and not str(value).isdigit():
            problems.append(f"{value!r} is not a readable prefix")
        if any(str(value).startswith(prefix) for prefix in PREMIUM_PREFIXES):
            problems.append(f"{value!r} is premium or premium-shaped: {REFUSED['premium-or-irsr-target']}")
        if own_dids and str(value) in {str(did) for did in own_dids}:
            problems.append(f"{value!r} is one of our own numbers, so the rule forwards to itself")
    for key in ("call", "message"):
        mode = rule_.get(key)
        if mode and mode not in (CALL_MODES if key == "call" else MESSAGE_MODES):
            problems.append(f"{key} mode {mode!r} is not one of the {key} modes")
    if rule_.get("call") in ("busy", "no_answer") and not rule_.get("window"):
        problems.append(f"{rule_['call']} needs the ring timer decided, and the timer is the feature")
    return problems


def chain_problem(forwards):
    """a loop of forwards rings two legs forever and bills whoever owns the numbers. find it here."""
    problems = []
    for source, target in forwards.items():
        if str(source) == str(target):
            problems.append(f"{source} forwards to itself")
    for start in forwards:
        seen, node = [], start
        while node in forwards and node not in seen:
            seen.append(node)
            node = forwards[node]
        if node in seen:
            problems.append("a loop: " + " -> ".join(seen + [node]))
            break
    return problems


def loop_safe(forwards):
    return not chain_problem(forwards)
