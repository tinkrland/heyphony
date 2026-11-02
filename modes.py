"""the three modes, as data, so the readme cannot drift from them.

this branch is instructions, so the instructions are the product. keeping them in a dict is not
bureaucracy: it means `--mode local --host macos` can print the errand for that pairing, an agent can
ask which steps are its own, and the test suite can compare every claim in readme.md against the
same dict a caller reads. a page that says one thing and a planner that says another is the failure
mode this file exists to prevent.

stdlib only, and it imports nothing from the heyphony package. this branch is an orphan on purpose:
it describes where the package runs, it is not part of it.
"""
import argparse
import json
import sys

MODES = {
    "local": {
        "label": "an agent on a computer you already have",
        "row": "a computer you own",
        "where": "the computer the agent already runs on",
        "registration": "on that computer, written by `heyphony connect`",
        "secret": "~/.config/linphone/linphonerc, mode 0600, on your own disk",
        "catcher": "the same computer, on a port you choose",
        "registration_survives_sleep": False,
        "calls_while_asleep": False,
        "texts_while_asleep": True,
        "secret_leaves_disk": False,
        "inbound_port": "only for the catcher",
        "cells": {"registration_survives_sleep": "no", "calls_while_asleep": "no",
                  "texts_while_asleep": "yes", "secret_leaves_disk": "no",
                  "inbound_port": "only for the catcher"},
        "rotation": None,
        "depends_on": "which computer, so ask before answering",
        "why": "cheapest by a wide margin, and the only mode where the answer starts with a question",
        "cost": "the machine you already have, plus about a dollar a month for the did",
    },
    "own-vm": {
        "label": "an agent with a computer of its own",
        "row": "a computer of its own",
        "where": "a container on your machine, or a vm in the cloud",
        "registration": "on that host, kept alive by a client that does not close a lid",
        "secret": "on that host's disk, which may be somebody else's disk",
        "catcher": "the same host, reachable from the internet",
        "registration_survives_sleep": True,
        "calls_while_asleep": True,
        "texts_while_asleep": True,
        "secret_leaves_disk": True,
        "inbound_port": "only for the catcher, and a public ip answers it by existing",
        "cells": {"registration_survives_sleep": "yes", "calls_while_asleep": "yes",
                  "texts_while_asleep": "yes", "secret_leaves_disk": "yes, to the host you rent",
                  "inbound_port": "only for the catcher, and a public ip answers it by existing"},
        "rotation": None,
        "depends_on": "whether it is a container at home or a vm with a public address",
        "why": "the registration and the catcher keep running when your laptop closes",
        "cost": "one small instance, billed for being reachable rather than for being busy",
    },
    "spawnable": {
        "label": "an agent using a spawnable",
        "row": "a spawnable",
        "where": "a guest with a lifecycle, beside a durable host that holds the number",
        "registration": "on the durable host, never in the body that gets shredded",
        "secret": "on the durable host; the guest reads the inbox over the control plane and holds no credential",
        "catcher": "on the durable host, because a catcher in a burn lane misses everything after the burn",
        "registration_survives_sleep": "only with a duty cycle",
        "calls_while_asleep": "only in the window",
        "texts_while_asleep": True,
        "secret_leaves_disk": False,
        "inbound_port": "no, the durable host carries it",
        "cells": {"registration_survives_sleep": "only with a duty cycle",
                  "calls_while_asleep": "only in the window", "texts_while_asleep": "yes",
                  "secret_leaves_disk": "no, the guest never holds it",
                  "inbound_port": "no, the durable host carries it"},
        "rotation": "the guest rotates, the registration does not",
        "depends_on": "whether the durable host is a mode one or mode two machine",
        "why": "burnable bodies for the work, one registration for the number",
        "cost": "a durable host plus whatever the guest costs while it exists",
    },
}

HOSTS = {
    "macos": {
        "label": "macOS, which is usually a laptop that sleeps",
        "install": "brew install baresip",
        "keep_it_up": "a launchd agent for `heyphony serve`",
        "audio": "a microphone permission prompt appears once, and dismissing it records silence",
        "catcher_reach": "a tunnel or a dynamic dns name, because a laptop changes networks",
        "honest": "a closed lid is a sleeping machine, so calls do not ring",
        "points": ["brew install baresip", "launchd", "closed lid", "microphone permission"],
    },
    "linux": {
        "label": "linux, desktop or a box in the corner",
        "install": "apt install baresip, or your distro's equivalent",
        "keep_it_up": "a systemd --user unit for `heyphony serve`",
        "audio": "a desktop with a sound card speaks and listens",
        "catcher_reach": "the port opened deliberately, with a long token on the webhook path",
        "honest": "a box that is plugged in and never closed answers at three in the morning",
        "points": ["apt install baresip", "systemd --user", "sound card"],
    },
    "server": {
        "label": "a server you ssh into",
        "install": "apt install baresip, or your distro's equivalent",
        "keep_it_up": "a systemd unit, which is the least dramatic of the five",
        "audio": "no audio device, so it registers, dials and records, and cannot be a speakerphone",
        "catcher_reach": "the port opened to the internet, so the token is doing real work",
        "honest": "right for every rail except a live voice conversation",
        "points": ["no audio device", "speakerphone", "token"],
    },
    "windows-wsl": {
        "label": "windows, through wsl2",
        "install": "the cli and the catcher inside wsl2, and a sip client on the windows side",
        "keep_it_up": "a wsl2 service or a scheduled task; the least proven of the five",
        "audio": "needs a pulse bridge or a softphone on the windows side, because wsl2 has no audio device by default",
        "catcher_reach": "wsl2 port forwarding, which is a moving target across reboots",
        "honest": "the least proven of the five, and mode two is often the better answer for the same money",
        "points": ["wsl2", "pulse bridge", "least proven"],
    },
    "always-on-box": {
        "label": "a small always-on box, which is the shape most people actually want",
        "install": "apt install baresip on a raspberry pi, a mini pc, or an old laptop with the lid taped shut",
        "keep_it_up": "a systemd unit and a machine that is simply never turned off",
        "audio": "a usb sound card if it needs to speak, and nothing if it only needs to catch",
        "catcher_reach": "one port forward on your router, once",
        "honest": "your power bill, your network and your patching, in exchange for the secret staying on a disk you can hold",
        "points": ["raspberry pi", "four watts", "power bill"],
    },
}

HOUSING = {
    "container": {
        "label": "a container on the computer you already have",
        "registration": "outbound, so it works fine from behind nat",
        "catcher_reach": "needs a tunnel or a port forward, because inbound does not come for free",
        "network": "host networking, because rtp picks a wide port range",
        "state": "a volume for ~/.config/linphone and ~/.local/share/telephony, or the number and the inbox are lost with the container",
        "honest": "the container solves the dependency problem and not the network problem",
        "points": ["host networking", "volume", "tunnel or a port forward"],
    },
    "cloud-vm": {
        "label": "a vm in the cloud",
        "registration": "on the instance's disk, kept alive by a process that restarts",
        "catcher_reach": "a public ip, which solves the inbound half by existing",
        "network": "a firewall rule for the catcher's port",
        "state": "the instance's disk, which is somebody else's disk",
        "honest": "no audio device, so it records a call and cannot hold a conversation without a media rail",
        "points": ["public ip", "no audio device", "somebody else's disk"],
    },
    "container-on-server": {
        "label": "the same shape without the paperwork",
        "registration": "on a server you already run",
        "catcher_reach": "a tunnel in front, one port",
        "network": "host networking, one process tree",
        "state": "one volume and restart: always",
        "honest": "the answer for somebody with a homelab and no interest in a cloud account",
        "points": ["homelab", "restart: always", "one volume"],
    },
}

SHARED = [
    "the did comes from a provider in every mode, about a dollar a month at the cheap end",
    "the number is classified as voip whatever you run behind it",
    "the install is the same command in all three modes",
    "paying for the number is a human act, in every mode, including the one whose ordering chain is scriptable",
    "fetching the sip password out of a provider dashboard is a human act the first time",
    "the sip secret lands at mode 0600 because it is a password in a text file",
]

def mode(name):
    try:
        return dict(MODES[name], mode=name)
    except KeyError:
        raise KeyError(f"no mode called {name!r}; the modes are {sorted(MODES)}")


def host(name):
    try:
        return dict(HOSTS[name], host=name)
    except KeyError:
        raise KeyError(f"no host called {name!r}; the hosts are {sorted(HOSTS)}")


def housing(name):
    try:
        return dict(HOUSING[name], housing=name)
    except KeyError:
        raise KeyError(f"no housing called {name!r}; the housing are {sorted(HOUSING)}")


def plan(mode_name, host_name=None, housing_name=None):
    """the errand for one pairing, with the steps a process can do and the ones only a person can."""
    chosen = mode(mode_name)
    answer = {
        "mode": mode_name,
        "label": chosen["label"],
        "where": chosen["where"],
        "registration": chosen["registration"],
        "secret": chosen["secret"],
        "steps": [
            "install the package: curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh",
            "heyphony setup select sip   pick a provider, then a did, then paste the credentials",
            "heyphony connect           write the registration on the host that is going to hold it",
            "heyphony serve             catch the provider's text webhook",
            "heyphony hooks <provider>  print the url to paste into the provider's dashboard",
            "heyphony doctor            say what is registered and what is still only designed",
            "one real message, sent by a person, proves the lane",
        ],
        "human": [
            "pay for the number, because a purchase is a purchase",
            "paste the sip username and password from the provider dashboard, once",
        ],
        "caveats": [chosen["honest"] if "honest" in chosen else chosen["why"]],
        "shared": SHARED,
    }

    if mode_name == "local":
        if not host_name:
            answer["needs"] = "host"
            answer["flag"] = "--host"
            answer["options"] = sorted(HOSTS)
            answer["why"] = chosen["depends_on"]
            return answer
        picked = host(host_name)
        answer["host"] = host_name
        answer["host_label"] = picked["label"]
        answer["steps"] = [
            f"install: {picked['install']}",
            "install the package: curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh",
            "heyphony setup select sip   pick a provider, then a did, then paste the credentials",
            "heyphony connect           write the registration on this computer",
            f"keep the catcher up: {picked['keep_it_up']}",
            f"give the provider a url it can reach: {picked['catcher_reach']}",
            "heyphony hooks <provider>  print the url to paste into the provider's dashboard",
            "heyphony doctor            say what is registered and what is still only designed",
            "one real message, sent by a person, proves the lane",
        ]
        answer["audio"] = picked["audio"]
        answer["caveats"] = [picked["honest"]]

    elif mode_name == "own-vm":
        if not housing_name:
            answer["needs"] = "housing"
            answer["flag"] = "--housing"
            answer["options"] = sorted(HOUSING)
            answer["why"] = chosen["depends_on"]
            return answer
        picked = housing(housing_name)
        answer["housing"] = housing_name
        answer["housing_label"] = picked["label"]
        answer["steps"] = [
            "install the package on the host: curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh",
            "heyphony setup select sip   pick a provider, then a did, then paste the credentials",
            "heyphony connect           write the registration on that host",
            f"network: {picked['network']}",
            f"state: {picked['state']}",
            "heyphony serve             catch the provider's text webhook",
            f"reach the catcher: {picked['catcher_reach']}",
            "heyphony doctor            say what is registered and what is still only designed",
            "one real message, sent by a person, proves the lane",
        ]
        answer["caveats"] = [picked["honest"]]

    else:
        answer["steps"] = [
            "pick and stand up the durable host first: a mode one or mode two machine",
            "on that host: heyphony setup select sip, then heyphony connect, then heyphony serve",
            "on the guest: point the agent at the inbox over the control plane, and never copy the sip secret into it",
            "the guest reads with: heyphony open messages --unread",
            "if the durable host is itself a guest, give it a duty cycle and state the window in writing",
            "heyphony connect --on guest   only to prove registration from inside a guest, never to serve",
            "heyphony doctor on the durable host, then one real message, is what proves the lane",
        ]
        answer["caveats"] = [
            "a registration cannot live in a body you are going to burn",
            "a number that only rings while a guest is up is dead at three in the morning",
        ]

    return answer


def compare():
    """the table the readme prints, built from the same dict, so a cell cannot disagree."""
    columns = ("registration_survives_sleep", "calls_while_asleep", "texts_while_asleep",
               "secret_leaves_disk", "inbound_port")
    rows = []
    for name, entry in MODES.items():
        row = {"mode": name, "row": entry["row"]}
        row.update(entry["cells"])
        rows.append(row)
    return {"columns": list(columns), "rows": rows, "shared": SHARED}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="modes", description="where the machine holding the number lives, as json")
    parser.add_argument("--mode", choices=sorted(MODES))
    parser.add_argument("--host", choices=sorted(HOSTS))
    parser.add_argument("--housing", choices=sorted(HOUSING))
    parser.add_argument("--compare", action="store_true", help="the table from the readme, as data")
    parser.add_argument("--list", action="store_true", help="the three modes and what each depends on")
    args = parser.parse_args(argv)

    if args.compare:
        print(json.dumps(compare(), indent=2, sort_keys=True))
        return 0
    if args.list or not args.mode:
        print(json.dumps({name: {"label": entry["label"], "depends_on": entry["depends_on"]}
                          for name, entry in MODES.items()}, indent=2, sort_keys=True))
        return 0
    print(json.dumps(plan(args.mode, args.host, args.housing), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
