"""the command surface for the mobile branch: one json object out, no prompts."""
import argparse
import json
import sys

import client
import mobile
import ring as ring_rail


def _out(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))


def main(argv=None):
    p = argparse.ArgumentParser(prog="mobile")
    p.add_argument("--setup", action="store_true", help="the branch in one json object")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("status")
    sub.add_parser("prove")

    cl = sub.add_parser("client")
    cl.add_argument("--shape", default="host-bridge")
    cl.add_argument("--remote-brain", action="store_true")
    cl.add_argument("--first-proof", action="store_true")
    cl.add_argument("--proven", action="store_true")
    cl.add_argument("--sourced", action="store_true")

    rg = sub.add_parser("ring")
    rg.add_argument("--channel", default="catcher")
    rg.add_argument("--proof", action="store_true")

    w = sub.add_parser("wake")
    w.add_argument("--row")

    sub.add_parser("answer")

    r = sub.add_parser("routes")
    r.add_argument("--route")

    v = sub.add_parser("verbs")
    v.add_argument("--backend", default="android-adb")

    c = sub.add_parser("checks")
    c.add_argument("--check")

    pl = sub.add_parser("plan")
    pl.add_argument("verb")
    pl.add_argument("--backend", default="android-adb")
    pl.add_argument("--pkg")
    pl.add_argument("--label")
    pl.add_argument("--text")

    a = p.parse_args(argv)

    if a.setup:
        _out(mobile.setup_plan())
        return 0
    if a.cmd == "status":
        _out(mobile.status())
    elif a.cmd == "prove":
        steps = mobile.setup_plan()["prove"]
        _out({"steps": steps, "count": len(steps),
              "first_success": ("one app opened and one screen read on an android we hold, then a tap that "
                                "came out of a real dump, then the same look on an iphone where only screen "
                                "is offered, and only then a hardware check a guest would fail")})
    elif a.cmd == "answer":
        _out({"paths": mobile.answer_paths(),
              "with_audio": mobile.answers_with_audio(),
              "short": ("waking the phone is solvable and answering is not the same question: a tapped answer on "
                        "a stock sip client is a call the agent cannot hear, so an agent that answers lives on "
                        "the host until we ship a client that joins a room")})
    elif a.cmd == "client":
        if a.sourced:
            _out({"components": client.SOURCED_FROM,
                  "borrowed": client.borrowed_components(),
                  "nobody_has": client.NOBODY_HAS,
                  "short": ("three of the five components already exist on other branches, so the client "
                            "is assembly rather than a build: callheavy owns the dial socket and the audio "
                            "rows, meetings owns the room, and what nobody has is the sip to room bridge")})
        elif a.proven:
            _out(client.attempt())
        elif a.first_proof:
            _out(client.first_proof(a.shape))
        else:
            _out({**client.choices(),
                  "plan": client.bridge_plan(a.shape, remote_brain=a.remote_brain),
                  "first_proof": client.first_proof(a.shape)})
    elif a.cmd == "ring":
        if a.proof:
            _out(ring_rail.first_proof())
        else:
            _out({"plan": ring_rail.ring_plan(a.channel), "events": ring_rail.RING_EVENTS,
                  "channels": ring_rail.NOTIFY, "pickup": ring_rail.PICKUP,
                  "refusals": ring_rail.REFUSED, "first_proof": ring_rail.first_proof(),
                  "short": ("the host sees the invite and answers at once, because a caller gives up in "
                            "thirty seconds and email is minutes. the notification rides beside the "
                            "answer rather than before it, and the agent takes over once it wakes")})
    elif a.cmd == "wake":
        if getattr(a, "row", None):
            _out(mobile.wake(a.row))
        else:
            _out({"rows": mobile.wake_rows(),
                  "short": ("registered is not ringing: android parks the app's network in doze and ios closes "
                            "the socket when the screen locks, so an idle phone rings only through push on ios, "
                            "a full screen intent plus a wake path on android, or the carrier's own forwarding "
                            "to the phone's number, where a person picks up instead of the agent")})
    elif a.cmd == "routes":
        if a.route:
            _out(mobile.route(a.route))
        else:
            _out({"recommended": mobile.recommend(),
                  "routes": {k: {"secret_on": v["secret_on"],
                                 "phone_keeps_it": v["phone_keeps_it"],
                                 "survives_phone_burn": v["survives_phone_burn"],
                                 "registrations": v["registrations"],
                                 "state": v["state"]} for k, v in mobile.LINE_ROUTES.items()}})
    elif a.cmd == "verbs":
        spec = mobile.BACKENDS.get(a.backend)
        if not spec:
            _out({"known": False, "known_backends": sorted(mobile.BACKENDS)})
            return 2
        _out({"backend": a.backend, "verbs": spec["verbs"], "why": spec["why"],
              "all_verbs": list(mobile.VERBS)})
    elif a.cmd == "checks":
        if a.check:
            _out(mobile.check(a.check))
        else:
            _out({"checks": mobile.CHECKS, "a_guest_fails": mobile.checks_a_guest_fails()})
    elif a.cmd == "plan":
        kw = {k: v for k, v in (("pkg", a.pkg), ("label", a.label), ("text", a.text)) if v}
        _out(mobile.plan(a.verb, backend=a.backend, **kw))
    else:
        _out(mobile.status())
    return 0


if __name__ == "__main__":
    sys.exit(main())
