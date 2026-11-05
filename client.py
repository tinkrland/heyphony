"""client: the app that puts the call's voice where the agent can reach it.

the branch reached this honestly. host-holds-the-line is right until the agent has to be the
callee, and every shape after that needs a client, because a stock sip app sends the voice to the
handset's earpiece and nowhere else.

two shapes, and the order is deliberate: the host bridge first, because it can be built and proven
with no phone in the path and no app store, and the phone app second, because it is the only shape
that answers on the phone itself. neither is claimed. both are written down far enough that the
first one can be attempted by someone with a machine that has audio.
"""

COMPONENTS = {
    "sip-leg": {
        "what": "something registers the did and holds the call",
        "why": "one did is one registration, so this is the same decision as the line routes, seen from the client's side",
    },
    "agent-ear": {
        "what": "the far end's voice, captured where a process can read it",
        "why": "on a handset the media lands in the earpiece, which is why the tap-answer row has no ears",
    },
    "agent-mouth": {
        "what": "our tts, played into the call as if it were a microphone",
        "why": "a headless host has no microphone, so the mouth is a virtual source rather than a device",
    },
    "room-leg": {
        "what": "both tracks published to the livekit room the meetings rail already describes",
        "why": "only needed when the agent's brain lives somewhere other than the host holding the call",
    },
    "consent": {
        "what": "the agent says what it is, and nothing is recorded that the room was not told about",
        "why": "a call where the human believes they reached a person is the same lie as borrowed identity",
    },
}

SHAPES = {
    "host-bridge": {
        "what": ("baresip on the host answers, pipewire carries the voice: tts into a null sink that is "
                 "remapped as the mic, and the far end captured off the same sink's monitor"),
        "components": ("sip-leg", "agent-ear", "agent-mouth", "consent"),
        "with_a_remote_brain": ("sip-leg", "agent-ear", "agent-mouth", "room-leg", "consent"),
        "wins": ("no phone in the call, no app to sign, and it works on the machine that already holds "
                 "the did, which is the configuration the rest of this repo is built around"),
        "costs": ("a linux host with pipewire and audio is required, and the audio path is the part that "
                  "cannot be tested by this branch's suite"),
        "proves_here": False,
        "needs": ["a registered did on the host, which is main's errand",
                  "pipewire with a null sink and a remap source",
                  "baresip with ctrl_tcp, so a process can answer and hang up without a keyboard"],
        "state": "designed",
    },
    "phone-app": {
        "what": ("one android app that registers the did, rings through a full screen intent, publishes "
                 "its microphone to the room and plays the agent's track into the call"),
        "components": ("sip-leg", "agent-ear", "agent-mouth", "room-leg", "consent"),
        "with_a_remote_brain": ("sip-leg", "agent-ear", "agent-mouth", "room-leg", "consent"),
        "wins": ("the phone answers by itself, so the ringing and the hardware checks live in the same "
                 "app on the same device, which is the only shape that survives the phone being the callee"),
        "costs": ("an android build, a signing identity and a device to test on, none of which this branch "
                  "can do, so it stays a spec rather than progress"),
        "proves_here": False,
        "needs": ["an android toolchain and a signing identity",
                  "the linphone or pjsip sdk for the sip leg, and the livekit android sdk for the room",
                  "the wake levers already written down: doze whitelist, foreground service, full screen intent"],
        "state": "designed",
    },
}

REFUSED = {
    "agent-hears-itself": ("a bridge that subscribes to the track it publishes is an echo loop, so the "
                           "mouth is never subscribed back, and the default is half duplex"),
    "silent-recording": ("no recorder opens unless the room was told, and the recordings that do exist "
                         "are transcripts rather than audio unless somebody asked for audio"),
    "unlabelled-bot": ("the agent says what it is on the first turn. a human who believes they reached a "
                       "person has been lied to, and that is refused here the same way borrowed identity is"),
    "cold-answer": ("the invite is the permission. a client that answers a number nobody dialled is the "
                    "same cold join the meetings rail refuses"),
    "re-encode-forever": ("the voice crosses two codecs at most, and a shape that decodes and re-encodes "
                          "for the length of the call is a latency bug dressed as a design"),
}


def shape(name="host-bridge"):
    if name not in SHAPES:
        raise KeyError(f"no such shape: {name}. the two that exist are {sorted(SHAPES)}")
    return SHAPES[name]


def first_shape():
    """the one to build first, and the reason, kept to one sentence a reader can act on."""
    return {"shape": "host-bridge",
            "because": ("it needs no phone, no signing identity and no app store, and it runs on the "
                        "machine that already holds the did, so the first call it proves is a real one")}


def components_for(name="host-bridge", remote_brain=False):
    row = shape(name)
    keys = row["with_a_remote_brain"] if remote_brain else row["components"]
    return [{"name": key, **COMPONENTS[key]} for key in keys]


def bridge_plan(name="host-bridge", remote_brain=False):
    """the steps in the order they have to happen, with the commands that are not guesses marked as such."""
    if name == "host-bridge":
        steps = [
            {"step": "hold the line", "does": "sip-leg",
             "how": ["baresip", "-f", "<confdir baresip owns>"],
             "note": ("accounts file holds the did and the provider's registration host. enable the "
                      "ctrl_tcp module so a process can answer and hang up: confirm the flag against the "
                      "man page on the box, the command here is the shape and not a tested line")},
            {"step": "give it a mouth", "does": "agent-mouth",
             "how": ["pactl", "load-module", "module-null-sink", "sink_name=agent"],
             "note": ("then remap agent.monitor as a source named agent-mic, which is the same two "
                      "commands audio.py already keeps for native clients")},
            {"step": "play the tts into that sink", "does": "agent-mouth",
             "how": ["pw-play", "--target", "agent", "<the tts wav>"],
             "note": "point baresip's microphone at agent-mic, and the caller hears the agent"},
            {"step": "listen to the caller", "does": "agent-ear",
             "how": ["pw-record", "--target", "agent.monitor", "far-end.wav"],
             "note": ("the monitor is the far end's voice as the host played it. record in segments on "
                      "voice activity rather than one file per call")},
            {"step": "publish, if the brain is elsewhere", "does": "room-leg",
             "how": ["<the room client, publishing far-end.wav as a track and subscribing the tts track>"],
             "note": "skipped when the agent runs on the same host, which is the cheaper first proof"},
            {"step": "say what you are", "does": "consent",
             "how": ["<first turn of the call>"],
             "note": "an agent that opens with its name is the whole refusal honoured in one sentence"},
        ]
    else:
        steps = [
            {"step": "build the app", "does": "sip-leg",
             "how": ["<android project with the sip sdk and the livekit sdk>"],
             "note": "the sip leg and the room leg are two sdk integrations in one process"},
            {"step": "let it ring loudly", "does": "sip-leg",
             "how": ["adb shell cmd deviceidle whitelist +<pkg>"],
             "note": "plus a foreground service and a full screen intent, which is the WAKE table's lever"},
            {"step": "publish the microphone", "does": "agent-ear",
             "how": ["<publish the mic track to the room on answer>"],
             "note": "the far end's voice is a subscribed track, not a recording"},
            {"step": "play the agent", "does": "agent-mouth",
             "how": ["<attach the subscribed agent track to the call audio route>"],
             "note": "the earpiece, or the speakerphone, which is an app decision and not ours"},
            {"step": "say what you are", "does": "consent",
             "how": ["<first turn of the call>"],
             "note": "same sentence, same refusal"},
        ]
    return {"shape": name, "remote_brain": remote_brain, "steps": steps,
            "state": shape(name)["state"], "proves_here": shape(name)["proves_here"]}


def room_contract():
    """what the room is allowed to carry, so a client build has something to be wrong against."""
    return {"identity": "the did, because the call is the identity that matters to the person on it",
            "publish": ["the far end's voice as one track", "the agent's tts as one track"],
            "subscribe": "the agent's own track, never, which is the echo refusal in one line",
            "mute": "the mouth is muted while the ear is live unless a barge-in is wanted",
            "records": "off unless the room is told, and transcripts by preference"}


def first_proof(name="host-bridge"):
    if name == "host-bridge":
        return {"call_it": "dial the did from a handset",
                "passes_when": ("baresip answers, the handset hears the tts, and a sentence spoken into "
                                "the handset comes back as a transcript"),
                "fails_loudly_when": ("the handset hears silence, which is a wrong source in the accounts "
                                      "file, or hears the agent twice, which is the echo refusal broken")}
    return {"call_it": "dial the did from another handset",
            "passes_when": ("the phone rings with the screen off, our tap answers, the agent's voice "
                            "arrives in the earpiece, and the caller's voice reaches the agent"),
            "fails_loudly_when": ("the phone never rings, which is doze, or the call connects and nothing "
                                  "is published, which is the app rather than the network")}


def choices():
    return {"first": first_shape(), "shapes": {k: {"state": v["state"], "proves_here": v["proves_here"]}
                                              for k, v in SHAPES.items()},
            "contract": room_contract(), "refusals": sorted(REFUSED)}
