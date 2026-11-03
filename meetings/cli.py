"""meetings cli: the join plan, the microphone rail, and the lane's own state, as json.

every verb answers a question rather than performing the human's part. `join` builds the plan and the
token but does not put a participant in a room, because that is a browser act with an invite in hand.
"""
import argparse
import json
import os
import sys

from . import meetings_lane as lane
import audio


def _out(payload):
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def setup_payload(env=None):
    env = env if env is not None else os.environ
    return {
        "what_this_is": "one branch: the room people are already in, joined as a participant.",
        "lane": lane.LANE,
        "platforms": {name: {"join": spec["join"], "gate": list(spec["gate"]),
                             "state": spec["state"], "signal": spec["signal"]}
                      for name, spec in lane.PLATFORMS.items()},
        "rails": lane.RAILS,
        "open": [name for name, spec in lane.PLATFORMS.items()
                 if all(env.get(gate) for gate in spec["gate"])],
        "readiness": audio.readiness(env),
        "refused": {"cold join": "a link is not an invitation",
                    "recording by default": "capture is the host's decision, not ours",
                    "publishing": "a stream is a different rail with a different consent problem"},
    }


def status_payload(env=None):
    env = env if env is not None else os.environ
    return {
        "lane": lane.LANE,
        "platforms": {name: {"state": spec["state"],
                             "missing": [gate for gate in spec["gate"] if not env.get(gate)]}
                      for name, spec in lane.PLATFORMS.items()},
        "audio": audio.readiness(env),
    }


def cmd_setup(args):
    _out(setup_payload())


def cmd_status(args):
    _out(status_payload())


def cmd_join(args):
    _out(lane.join_plan(args.platform, args.meeting))


def cmd_audio(args):
    if args.audit:
        _out(audio.audit())
        return
    _out(audio.meeting_mic(args.platform, args.wav, args.client))


def cmd_sign(args):
    _out(lane.sign_zoom_join(args.meeting, role=args.role))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="meetings", description=lane.LANE["relay"])
    parser.add_argument("--setup", action="store_true", help="the whole plan, in lane shape")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="the plan").set_defaults(func=cmd_setup)
    sub.add_parser("status", help="every platform, and what it is missing").set_defaults(func=cmd_status)

    join = sub.add_parser("join", help="what joining this room takes")
    join.add_argument("--platform", default="zoom", choices=lane.rails.platform_names())
    join.add_argument("--meeting", required=True)
    join.set_defaults(func=cmd_join)

    mic = sub.add_parser("audio", help="the microphone rail, and which parts are free software")
    mic.add_argument("--platform", default="zoom")
    mic.add_argument("--client", default=None, help="a native client: zoom-client, linphone, baresip")
    mic.add_argument("--wav", default="agent-voice.wav")
    mic.add_argument("--audit", action="store_true")
    mic.set_defaults(func=cmd_audio)

    sign = sub.add_parser("sign", help="just the join token, when that is all you need")
    sign.add_argument("--meeting", required=True)
    sign.add_argument("--role", type=int, default=0)
    sign.set_defaults(func=cmd_sign)

    args = parser.parse_args(argv)
    if args.setup:
        return cmd_setup(args)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
