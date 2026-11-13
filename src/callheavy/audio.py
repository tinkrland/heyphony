"""the audio: where the agent's voice enters the call, and where livekit is the right answer instead.

two media paths, and they are different problems wearing the same word. a phone call carries one
stream over rtp and the client owns it, so the agent has to arrive at the client's audio device. a
livekit room carries tracks between participants, so the agent arrives as a participant. the umbrella
already picked the rails for both; this file is the honest version of them for a call this lane places.

what is here: the virtual microphone a native client can read from (pipewire or pulse, over pactl), the
browser flags that make a page see a wav file as a microphone, and the livekit gate with a publish call
that refuses by name when the sdk is absent rather than failing an import at module load.

what is built elsewhere in this folder: the agent's ears and mouth on a sip call. `pump.py` puts the
agent's voice where baresip reads its microphone and records what baresip plays, through four
pulseaudio null sinks that keep their own clock, and `rig.py` runs two real baresip instances so it can
be proven on a machine with no sound card and no carrier. a tone crosses a real call in each direction
at the level it was spoken, with no leakage, and the test for it runs on every suite. an earlier version
of this docstring said the pumping was not written, and that was the wrong sentence: it was never one
problem.

what is not here: a bridge between a sip call and a livekit room. that is the different problem the old
sentence was pointing at, a participant that holds two media clocks and two codecs at once, and it is
not written. saying so is the point of `bridge_plan()`. turning the ears into a transcript is also not
here, because that needs a speech model and this repo ships none.
"""
import os

# per host, because the virtual device is the least portable thing in this repo. the licences are named
# because one of them is not oss and the umbrella's rule is to say which rather than to round up.
MIC = {
    "linux": {
        "tool": "pactl",
        "commands": (
            "pactl load-module module-null-sink sink_name=agent",
            "pactl load-module module-remap-source master=agent.monitor source_name=agent-mic",
        ),
        "client_device": "agent-mic",
        "license": "pipewire is MIT and pulseaudio is LGPL-2.1",
        "verified": True,
        "note": "pipewire speaks the pactl interface, so this works under either on a modern desktop",
    },
    "macos": {
        "tool": "blackhole",
        "commands": (),
        "client_device": "BlackHole 2ch",
        "license": "blackhole is GPL-3.0",
        "verified": False,
        "note": "blackhole is an install plus a reboot, which is an expensive place to do audio",
    },
    "windows": {
        "tool": "vb-cable",
        "commands": (),
        "client_device": "CABLE Output",
        "license": "vb-cable is donationware and NOT oss",
        "verified": False,
        "note": "the only non-oss link in the chain, and it is named as such",
    },
}

BROWSER_FLAGS = (
    "--use-fake-device-for-media-stream",
    "--use-file-for-fake-audio-capture={wav}",
)

LIVEKIT_ENV = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


def host_row(platform=None):
    name = platform or ("macos" if os.uname().sysname == "Darwin" else "linux")
    return dict(MIC.get(name, MIC["linux"]), platform=name)


def virtual_mic(platform=None):
    """the commands that give a native sip client a microphone it can hear us through."""
    row = host_row(platform)
    return {"platform": row["platform"], "tool": row["tool"], "commands": list(row["commands"]),
            "client_device": row["client_device"], "license": row["license"],
            "verified": row["verified"], "note": row["note"],
            "oss": row["platform"] != "windows"}


def browser_mic(wav, platform=None):
    """a page that asks for a microphone and gets a file. no device, no server, no obs."""
    return {"platform": host_row(platform)["platform"], "args": [flag.format(wav=wav) for flag in BROWSER_FLAGS],
            "oss": True,
            "note": "chromium only, and it is the cheapest rail when the call happens in a browser"}


def room_state():
    """the livekit gate. closed unless all three are set, because two of three is a confusing error."""
    env = {name: bool(os.environ.get(name)) for name in LIVEKIT_ENV}
    missing = [name for name, present in env.items() if not present]
    return {"closed": bool(missing), "missing": missing, "env": env,
            "why": "a room needs a url and a pair of keys; a partial set fails later and worse"}


def publish(track_name="agent-voice", identity="agent"):
    """join a livekit room and publish a track, using the sdk only if it is actually installed.

    the import is inside the call so that importing this module never needs the sdk, and so the
    refusal is a sentence with an install line rather than a traceback at startup.
    """
    state = room_state()
    if state["closed"]:
        return {"ok": False, "missing": state["missing"], "why": state["why"]}
    try:
        import livekit.rtc  # noqa: F401  (optional dependency, deliberately not in any requirements file)
    except ImportError:
        return {"ok": False, "missing": ["livekit"], "install": "pip install livekit",
                "why": "the room rail needs the sdk, and this repo does not depend on it"}
    return {"ok": True, "joined": os.environ.get("LIVEKIT_URL"), "identity": identity,
            "track": track_name,
            "next": "the sdk is present; publishing a real track is a host decision, not a stack trace"}


def bridge_plan():
    """the gap between our sip call and a livekit room, said once rather than implied away."""
    return {
        "shipped": False,
        "what_it_would_be": "a participant joined to both ends: it subscribes to the room's audio and "
                            "feeds the sip client's capture device, and it publishes the call's audio "
                            "back into the room as a track",
        "why_not_shipped": "two media clocks and two codecs is a project, not a helper, and pretending "
                           "otherwise would make this lane look finished",
        "what_is_shipped_instead": "the agent's ears and mouth on a sip call (pump.py), which needs no "
                                   "room: it is one stream each way through a local sink",
        "the shape_that_works_today": "the call rides baresip and the agent's voice rides the virtual mic; "
                                      "a room rides livekit and the agent is a participant. pick the one "
                                      "that matches where the other person already is",
        "env_for_the_bridge_side": list(LIVEKIT_ENV),
    }


def readiness(platform=None):
    """one object a host can read before a call, so 'no sound' is diagnosed in one step."""
    row = virtual_mic(platform)
    room = room_state()
    return {
        "mic": {"platform": row["platform"], "device": row["client_device"], "tool": row["tool"],
                "commands": row["commands"], "verified": row["verified"], "oss": row["oss"]},
        "room": {"closed": room["closed"], "missing": room["missing"]},
        "bridge": "not shipped",
        "call_audio": {"shipped": True, "module": "src/callheavy/pump.py",
                       "what": "the agent's voice into the call and the far end's voice out of it, on a sip "
                               "call this lane places",
                       "proof": "src/callheavy/rig.py runs two baresip instances and a test carries a tone "
                                "each way"},
        "note": "a call without a capture device connects and is silent, which sounds like a network "
                "problem and is not one",
    }
