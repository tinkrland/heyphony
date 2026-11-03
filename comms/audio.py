"""audio: how an agent gets heard in a room, and which pieces are free software.

owner: "for calls audio afaik we used obs virtual mic + livekit? should be oss."
half right, and the wrong half is worth writing down, because a virtual mic is not one
thing and only one of the ways to get one is oss and light.

three answers, cheapest first:

1. a browser we launch needs no audio device at all. chromium answers getUserMedia from a
   file with --use-fake-device-for-media-stream --use-file-for-fake-audio-capture=<wav>.
   for zoom web, meet and teams (all browser rooms here) this is the whole rail.
2. a NATIVE client (the zoom app, linphone, baresip) needs a real source: pipewire's null
   sink plus a remap source, two commands, both oss (mit).
3. obs is oss (gpl-2.0) and stays in the stack for scenes, not for audio: its virtual
   AUDIO capture is a macos add-on, not a linux feature, so it was never the mic on linux.
"""
import os

STACK = {
    "livekit": {
        "licence": "apache-2.0",
        "role": ("the webrtc transport: join the room the meeting already has as a participant, "
                 "publish tts, subscribe for stt"),
        "where": "meetings/ RAILS['audio']",
        "verified": False,
    },
    "chromium-flags": {
        "licence": "bsd-3-clause (chromium itself)",
        "role": ("the cheapest mic there is: --use-fake-device-for-media-stream plus "
                 "--use-file-for-fake-audio-capture=<wav> makes the browser answer getUserMedia "
                 "from a file"),
        "where": "the guest's own chrome, which we already launch",
        "note": "no audio server, no obs, no device at all. this is the rail for browser rooms",
        "verified": False,
    },
    "pipewire": {
        "licence": "mit (read from its COPYING, not a badge)",
        "role": ("a real source for native apps: a null sink and a remap source, two pactl calls, "
                 "so the app's microphone list shows a device called whatever we like"),
        "where": "linux host or guest with a native softphone",
        "verified": False,
    },
    "pulseaudio": {
        "licence": "lgpl-2.1",
        "role": "the same two calls on an older host; pipewire's pactl compatibility covers both",
        "verified": False,
    },
    "obs": {
        "licence": "gpl-2.0",
        "role": ("scenes and the virtual camera. its virtual audio device is a macos extra, "
                 "so on linux obs was never the mic, and nothing here needs it for one"),
        "where": "streaming/ drives it over obs-websocket",
        "verified": False,
    },
    "blackhole": {
        "licence": "gpl-3.0 (read from its LICENSE)",
        "role": "a virtual audio device for a macos host, because apple ships none",
        "verified": False,
    },
    "vb-cable": {
        "licence": "not oss (donationware, closed source)",
        "role": "the windows equivalent, named so nobody calls it free software",
        "verified": False,
    },
}

# licences that are free software, so the audit is a lookup and not a mood
OSS_LICENCES = {
    "apache-2.0", "mit", "bsd-3-clause", "gpl-2.0", "gpl-3.0", "lgpl-2.1", "lgpl-2.0",
}

NATIVE_CLIENTS = ("zoom-client", "linphone", "baresip", "teams-client")


def is_oss(name):
    return STACK[name]["licence"].split(" ")[0] in OSS_LICENCES


def audit():
    """which parts of the audio path are free software. the owner's question, as data."""
    return {
        "all_oss": all(is_oss(k) for k in ("chromium-flags", "pipewire", "pulseaudio", "livekit", "obs")),
        "oss": sorted(k for k in STACK if is_oss(k)),
        "not_oss": sorted(k for k in STACK if not is_oss(k)),
        "needed_for_audio": ["chromium-flags", "pipewire", "livekit"],
        "not_needed_for_audio": ["obs"],
        "note": ("every piece on the path is free software. obs is oss too, and still not the mic: "
                 "its virtual audio device lives on macos"),
    }


def browser_mic(wav_path):
    """chromium's own microphone. no server, no device, no obs."""
    return {
        "mode": "chromium-flags",
        "argv": ["--use-fake-device-for-media-stream",
                 f"--use-file-for-fake-audio-capture={wav_path}"],
        "why": "getUserMedia answers from a file, so a browser room gets a voice with nothing installed",
        "caveat": ("a wav, not a stream: fine for a tts line, wrong for live duplex unless the file is "
                   "rewritten as it speaks"),
    }


def virtual_mic(os_name="linux", sink="agent", source="agent-mic"):
    """a real microphone, for the apps that will not take a file."""
    os_name = (os_name or "linux").lower()
    if os_name in ("linux", "pipewire", "pulse", "pulseaudio"):
        return {
            "mode": "null-sink",
            "commands": [
                ["pactl", "load-module", "module-null-sink", f"sink_name={sink}"],
                ["pactl", "load-module", "module-remap-source",
                 f"master={sink}.monitor", f"source_name={source}"],
            ],
            "why": f"the app sees a microphone called {source}; we write into the {sink} sink",
            "note": "pipewire (mit) covers this through its pactl compatibility, pulseaudio (lgpl-2.1) is the older same",
        }
    if os_name in ("macos", "darwin", "osx"):
        return {
            "mode": "install-required",
            "device": "blackhole (gpl-3.0)",
            "why": "apple ships no virtual device; blackhole is the oss way to get one",
            "note": "an install and often a reboot, so a macos host is the expensive place to do audio",
        }
    if os_name == "windows":
        return {
            "mode": "install-required",
            "device": "vb-cable",
            "why": "the usual windows virtual cable",
            "note": "NOT oss. donationware, closed source, named rather than hidden",
        }
    return {"mode": "unknown", "why": f"no audio plan for {os_name!r}"}


def meeting_mic(platform, wav_path="agent-voice.wav", client=None):
    """which rail a given room needs. browser rooms get the file, native clients get the sink."""
    platform = (platform or "zoom").lower()
    if client in NATIVE_CLIENTS:
        plan = virtual_mic()
        plan.update({"platform": platform, "client": client})
        return plan
    if platform == "livekit":
        return {
            "mode": "livekit",
            "platform": platform,
            "why": "the room is livekit's own: publish the tts track as a participant (apache-2.0)",
            "gate": ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"),
            "fallback": browser_mic(wav_path),
        }
    plan = browser_mic(wav_path)
    plan["platform"] = platform
    plan["why"] = f"{platform}'s web client is a browser room, so the file is enough"
    return plan


def readiness(env=None):
    """what is actually set, so a plan cannot assume a rail that is closed."""
    env = env if env is not None else os.environ
    return {
        "livekit": bool(env.get("LIVEKIT_URL") and env.get("LIVEKIT_API_KEY") and env.get("LIVEKIT_API_SECRET")),
        "browser_room": True,  # we launch the browser, so the flags are always available
        "native_mic": bool(env.get("SPAWNABLES_AUDIO_SINK") or env.get("XDG_RUNTIME_DIR")),
        "obs": bool(env.get("OBS_WEBSOCKET_URL")),
    }
