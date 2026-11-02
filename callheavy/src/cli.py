"""callheavy: our own calls, arranged around a task instead of a script.

every subcommand prints one json object and exits. nothing prompts, because the caller may be a program
and a prompt is a hang. the two verbs that matter are `plan`, which dials nothing, and `dial`, which
needs `--run` and a named authoriser before it will ring anybody.
"""
import argparse
import json
import os
import pathlib
import sys
import time

from callheavy.src import audio, dial, host, task as tasks

STATE = pathlib.Path(os.environ.get("HEYPHONY_CALLHEAVY_DIR")
                     or "~/.local/share/telephony/callheavy").expanduser()


def _read_json(path):
    return json.loads(pathlib.Path(path).read_text()) if path else None


def _task(args):
    return tasks.task(args.goal, _read_json(args.schema), args.success, args.notes, args.language)


def _record_path(name):
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / f"{name}.json"


def _store(item, name):
    path = _record_path(name)
    path.write_text(json.dumps(item, indent=2, sort_keys=True))
    os.chmod(path, 0o600)
    return str(path)


def cmd_host(args):
    answer = host.write(args.did, args.user, args.password, args.sip_host, home=args.home,
                        platform=getattr(args, "platform", None), port=args.port, dry=args.dry)
    return answer, 0


def cmd_plan(args):
    item = _task(args)
    missing = tasks.clarifications(item, args.to)
    if missing:
        return {"ok": False, "problems": missing}, 1
    return {"ok": True, "task": item, "dial": f"sip:{args.to}",
            "socket": f"{args.socket}", "record": str(STATE),
            "note": "nothing was dialled. `dial --run` places it, and only then does a phone ring"}, 0


def cmd_dial(args):
    item = _task(args)
    missing = tasks.clarifications(item, args.to)
    if missing:
        return {"ok": False, "problems": missing}, 1
    if not args.authorized:
        return {"ok": False, "problems": [{"needs": "authorized", "flag": "--authorized",
                                          "why": "a call is somebody's phone ringing; the record says "
                                                 "who asked for it"}]}, 1
    target = f"sip:{args.to}"
    if not args.run:
        return {"ok": True, "sending": False, "dial": target, "socket": args.socket,
                "task": item, "authorized_by": args.authorized,
                "note": "plan only. --run sends the dial to baresip"}, 0

    host_name, _, port = args.socket.partition(":")
    result = dial.dial(target, host=host_name or "127.0.0.1", port=int(port or 4444),
                       settle=args.settle)
    record = {"task": item, "authorized_by": args.authorized, **result}
    record["record"] = _store(record, f"{args.to.lstrip('+')}-{int(time.time())}")
    return record, 0 if result.get("accepted") else 1


def cmd_mic(args):
    if args.wav:
        return {"ok": True, **audio.browser_mic(args.wav, args.platform)}, 0
    return {"ok": True, **audio.readiness(args.platform)}, 0


def cmd_room(args):
    return {"ok": True, **audio.publish(), "bridge": audio.bridge_plan()}, 0


def cmd_result(args):
    schema = _read_json(args.schema)
    source = _read_json(args.transcript) or {}
    extracted = _read_json(args.result) if args.result else None
    envelope = tasks.envelope(extracted, schema, transcript=source.get("transcript"),
                              outcome=source.get("call_outcome"))
    return {"ok": envelope["result_status"] == "available", **envelope}, 0


def cmd_prompt(args):
    item = _task(args)
    transcript = (_read_json(args.transcript) or {}).get("transcript") or []
    return {"ok": True, "prompt": tasks.extract_prompt(item, transcript)}, 0


def build(argv=None):
    parser = argparse.ArgumentParser(prog="callheavy",
                                     description="our own calls, arranged around a task")
    sub = parser.add_subparsers(dest="cmd")

    host_p = sub.add_parser("host", help="write the baresip config and accounts this lane drives")
    host_p.add_argument("--did", required=True)
    host_p.add_argument("--user", required=True)
    host_p.add_argument("--password", required=True)
    host_p.add_argument("--sip-host", required=True, help="the provider's sip hostname, not a sentence")
    host_p.add_argument("--home", help="where the baresip directory is")
    host_p.add_argument("--platform", choices=sorted(host.HOSTS))
    host_p.add_argument("--port", type=int, default=host.CTRL_PORT)
    host_p.add_argument("--dry", action="store_true", help="print the files instead of writing them")
    host_p.set_defaults(handler=cmd_host)

    for name, run in (("plan", cmd_plan), ("dial", cmd_dial)):
        p = sub.add_parser(name, help="print the call" if name == "plan" else "place it")
        p.add_argument("--goal", required=True, help="what the call is for, in words")
        p.add_argument("--to", required=True, help="one recipient in e164")
        p.add_argument("--schema", help="a json schema file: the fields to bring back")
        p.add_argument("--success", help="how either side would know it worked")
        p.add_argument("--notes", help="context the agent should have")
        p.add_argument("--language")
        p.add_argument("--socket", default=f"{host.CTRL_BIND}:{host.CTRL_PORT}")
        p.set_defaults(handler=run)

    dial_p = sub.choices["dial"]
    dial_p.add_argument("--authorized", help="who asked for this call")
    dial_p.add_argument("--run", action="store_true", help="actually dial")
    dial_p.add_argument("--settle", type=float, default=45.0, help="seconds to listen for the ending")

    mic_p = sub.add_parser("mic", help="the capture device, and what it costs")
    mic_p.add_argument("--wav", help="use a wav as a browser microphone instead of a device")
    mic_p.add_argument("--platform", choices=sorted(audio.MIC))
    mic_p.set_defaults(handler=cmd_mic)

    room_p = sub.add_parser("room", help="the livekit gate, and the bridge that is not shipped")
    room_p.set_defaults(handler=cmd_room)

    result_p = sub.add_parser("result", help="validate an extracted answer against its schema")
    result_p.add_argument("--schema", required=True)
    result_p.add_argument("--result", help="the extracted answer, as json")
    result_p.add_argument("--transcript", help="the call record this answer came from")
    result_p.set_defaults(handler=cmd_result)

    prompt_p = sub.add_parser("prompt", help="the question to ask our own model about a transcript")
    prompt_p.add_argument("--goal", required=True)
    prompt_p.add_argument("--schema", required=True)
    prompt_p.add_argument("--transcript", required=True)
    prompt_p.add_argument("--success")
    prompt_p.add_argument("--notes")
    prompt_p.add_argument("--language")
    prompt_p.set_defaults(handler=cmd_prompt)
    return parser


def main(argv=None):
    parser = build(argv)
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    answer, code = handler(args)
    print(json.dumps(answer, indent=2, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
