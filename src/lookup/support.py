"""support: what a line class implies about a service, and the probe that would answer it properly.

three questions get confused with each other, and only the first one is answerable from a numbering
plan:

- **can this range receive a text at all.** yes for a mobile range, no for a geographic one. this is
  evidence, from the plan.
- **would this service accept this number.** whatsapp, signal and imessage all verify by sending a code
  to the handset, by sms or by a spoken call. a range that cannot receive either cannot hold an account,
  which is a real answer for a landline and a useless answer for a mobile: two mobiles look identical
  to a numbering plan and behave identically to no service at all.
- **is this number registered right now.** only a probe answers that, and every probe either sends a
  code to somebody's phone or talks to an undocumented endpoint.

so the matrix below returns `possible`, `unlikely` or `unknown`, never a boolean that would be
invention, and `probe_plan()` says exactly what each service would need and what running it would do.
nothing here sends anything: `run_probe()` refuses, in the same voice as the rest of the package.
"""
from src.lookup import classify

POSSIBLE = "possible"
UNLIKELY = "unlikely"
UNKNOWN = "unknown"

# what each class can physically do, which is the part a plan knows
CLASS_RANK = {"mobile": 3, "voip": 2, "business numbering": 2, "landline": 1,
              "non-geographic numbering": 1, "personal numbering": 1, "pager": 0, "service range": 0,
              "premium rate": 0, "toll-free": 0, "freephone": 0, "unknown": -1}

SERVICES = {
    "imessage": {
        "verifies_by": ["a silent sms from apple, or an apple id already on the device"],
        "needs_text": True,
        "why_seen": "apple registers a handle, not a line type: an iphone with the number in it and the "
                    "carrier's sms reaching it",
        "probe": {"what": "an apple identity-services lookup, which is what a mac does when composing",
                  "consequence": "no code is sent, but the endpoint is undocumented and rate limited",
                  "wired": False}},
    "signal": {
        "verifies_by": ["an sms code", "a spoken call reading the code"],
        "needs_text": False,
        "why_seen": "signal accepts voice verification, so a landline is unlikely rather than impossible",
        "probe": {"what": "signal's registration state for the number",
                  "consequence": "the check needs a client key pair and reports whether somebody "
                                 "already holds the number, which is a privacy fact about them",
                  "wired": False}},
    "whatsapp": {
        "verifies_by": ["an sms code", "a spoken call reading the code"],
        "needs_text": False,
        "why_seen": "whatsapp's voice option means a landline is unlikely, not impossible",
        "probe": {"what": "whatsapp's registration endpoint",
                  "consequence": "the supported path sends an sms to that handset, so a stranger's "
                                 "phone buzzes for a check nobody there asked for",
                  "wired": False}},
    "sms": {
        "verifies_by": ["nothing: plain sms is the carrier, not a service"],
        "needs_text": True,
        "why_seen": "the one question here that the plan answers outright",
        "probe": None},
}

NOTE = ("the matrix is evidence, not a verdict. `possible` means the class can hold the account and the "
        "plan cannot tell you whether this particular number does; `unlikely` means the class needs the "
        "voice fallback to have any chance at all. a boolean per service is what a probe returns, and no "
        "probe is wired here.")


def _verdict(service, line):
    row = SERVICES[service]
    rank = CLASS_RANK.get(line["type"], -1)
    if rank == -1:
        return UNKNOWN, "the line type is unknown, so nothing follows about this service"
    if rank == 0:
        return UNLIKELY, f"a {line['type']} cannot receive a code, and every one of these verifies by code"
    if service == "sms":
        return (POSSIBLE if line.get("receive_text") is True else UNLIKELY,
                line.get("why") or "from the range's own class")
    if rank >= 3:
        return POSSIBLE, (f"a {line['type']} range can receive a code, and this service verifies by code; "
                          f"whether this number already has an account is a probe question")
    if rank == 2:
        return POSSIBLE, (f"a {line['type']} range can hold the account, and these services are known to "
                          f"accept voip numbers unevenly, so the class is permission and the network is "
                          f"the risk")
    return UNLIKELY, (f"a {line['type']} cannot receive an sms code; the only route is the voice "
                      f"fallback, which is why this is unlikely rather than impossible")


# an address and a handle answer a different set of services than a line does, and the difference is
# the whole point: a handle is how you reach somebody with no number at all
HANDLE_SERVICES = {
    "email": {"imessage": "an apple account is an address, so imessage is the one service an email "
                          "address can hold. the other three verify by a number",
              "others": "sms, signal and whatsapp verify by a code to a handset, so an address cannot "
                        "hold them"},
    "username": {"own": "a username is a way to start a chat without either side giving a number",
                 "others": "the username is a name on one platform. the other platforms and plain sms "
                           "route by number"},
}


def _handle_matrix(answer):
    """the services an address or a handle can hold, in the same rows a number gets."""
    services = []
    if answer["kind"] == "email":
        verdict = answer["imessage"]
        services.append({"service": "imessage", "verdict": verdict, "why": answer["why"],
                         "basis": "address class"})
        for name in ("sms", "signal", "whatsapp"):
            services.append({"service": name, "verdict": UNLIKELY,
                             "why": HANDLE_SERVICES["email"]["others"], "basis": "address class"})
    else:
        platform = answer["platform"]
        ambiguous = {row["platform"] for row in answer.get("also_read_as", [])} \
            if not answer.get("platform_certain") else set()
        for name in ("imessage", "signal", "whatsapp", "sms"):
            if name in ambiguous:
                services.append({"service": name, "verdict": UNKNOWN,
                                 "why": "the same string is a legal name on this platform too, and it "
                                        "would name a different account there",
                                 "basis": "username form"})
            elif name == platform:
                services.append({"service": name, "verdict": POSSIBLE if answer["valid"] else UNLIKELY,
                                 "why": answer.get("shape") or answer.get("why"),
                                 "basis": "username form"})
            else:
                services.append({"service": name, "verdict": UNLIKELY,
                                 "why": HANDLE_SERVICES["username"]["others"],
                                 "basis": "username form"})
    return services


def support(number, platform=None):
    """the line, the services, and no boolean that the evidence does not carry."""
    line = classify.classify(number, platform)
    if line.get("kind") in ("email", "username"):
        return {"number": number, "kind": line["kind"],
                "address" if line["kind"] == "email" else "handle": line,
                "services": _handle_matrix(line), "note": NOTE, "verified": False,
                "partial": False,
                "limits": {"services": "a handle answers for the platform it belongs to and for "
                                       "nothing else"}}
    services = []
    for name in ("sms", "imessage", "signal", "whatsapp"):
        verdict, why = _verdict(name, line)
        row = {"service": name, "verdict": verdict, "why": why,
               "basis": "numbering plan" if name == "sms" else "line class"}
        if SERVICES[name].get("probe"):
            row["probe_needed"] = True
        services.append(row)
    return {"number": number, "line": {k: line.get(k) for k in
                                       ("valid", "market", "type", "receive_text", "region", "why")},
            "services": services, "note": NOTE, "verified": False,
            "partial": bool(line.get("partial")),
            "limits": line.get("limits") or {"partial": "a partial lookup answers geography only"}}


def probe_plan(number, service=None):
    """what an honest probe would do, printed rather than performed."""
    services = [service] if service else [n for n, row in SERVICES.items() if row.get("probe")]
    unknown = [s for s in services if s not in SERVICES]
    if unknown:
        return {"ok": False, "why": "no such service", "known": sorted(SERVICES)}
    steps = []
    for name in services:
        probe = SERVICES[name]["probe"]
        if not probe:
            continue
        steps.append({"service": name,
                      "what": probe["what"],
                      "consequence": probe["consequence"],
                      "verifies_by": SERVICES[name]["verifies_by"],
                      "wired": probe["wired"]})
    return {"ok": True, "number": number, "probes": steps,
            "wired": [s["service"] for s in steps if s["wired"]],
            "why_not_run": ("no probe is wired here on purpose: each one either texts a stranger's "
                            "handset or leans on an undocumented endpoint, and a lookup tool that does "
                            "that quietly is a lookup tool nobody should install"),
            "gate": {"env": "HEYPHONY_LOOKUP", "value": "allowed",
                     "note": "the gate is read and honoured once a probe exists"}}
