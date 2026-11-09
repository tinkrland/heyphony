"""pump: the agent's ears and mouth on a call this lane places.

a call carries one stream each way, and baresip owns both of them. to take part in it, something has to
put the agent's voice where baresip reads its microphone, and take the far end's voice from where
baresip plays its speaker. that is all a pump is, and it needs no bridge, no second media clock and no
codec work, because baresip already does the one conversion that matters, g711 on the wire to pcm on a
local device. what the old docstring called "a real piece of software that is not written" is the
different problem of joining that call to a livekit room, and that stays named as not shipped.

the one rule that took a failed run to learn: **four sinks, never two.** the obvious layout has a sink
called `agent` whose monitor is also the microphone, and then the call's own playback lands in the same
sink and is transmitted straight back, which saturates the capture and looks like a tone that is too
loud. each direction therefore gets its own pair, so no output can reach its own input:

    agent_say   what the agent says. we play into it, baresip reads its monitor as the microphone
    agent_hear  what the call plays to the agent. baresip plays into it, we record its monitor
    far_say     the same pair for a stand-in far end, used by the self-test and nothing else
    far_hear

this is pulseaudio's null sink, which keeps its own clock, so it needs no sound card. that was measured
on a host with none (pipewire's was not, which is the whole story of the mobile branch).
"""
import os
import shutil
import subprocess
import time
import wave

SINKS = {
    "say": "agent_say",
    "hear": "agent_hear",
    "far_say": "far_say",
    "far_hear": "far_hear",
}

# the baresip keys that point a call at those sinks. the source is the *monitor* of a null sink, which is
# how a sink becomes something a program can read as a microphone.
AUDIO_KEYS = {
    "audio_player": "pulse,{hear}",
    "audio_source": "pulse,{say}.monitor",
    "audio_alert": "pulse,{hear}",
}

TOOLS = ("pactl", "paplay", "parecord")

# measured, not assumed: g711 over rtp through two null sinks keeps a tone's frequency and timing exactly
# and its level to within a fraction of a percent on the receiving side. the transmitting side applies a
# sink-input volume, which is a steady gain and not lost audio.
MEASURED = {
    "receive_level_error_pct": 0.55,
    "transmit_gain": 0.82,
    "cross_talk_ratio_min": 25000,
    "silence_peak_max": 1,
    "host": "debian 12 container, no sound card, pulseaudio 16.1, baresip 1.0.0 with pulse.so",
}


def tools_present(which=shutil.which):
    missing = [t for t in TOOLS if not which(t)]
    return {"ok": not missing, "missing": missing,
            "install": "apt install pulseaudio pulseaudio-utils" if missing else None}


def baresip_audio(sinks=None, rate=48000):
    """the audio lines for a baresip config, so the call is routed without anybody typing sink names."""
    names = dict(SINKS)
    names.update(sinks or {})
    lines = [f"{key}\t\t{value.format(**names)}" for key, value in AUDIO_KEYS.items()]
    lines += [f"ausrc_srate\t\t{rate}", f"auplay_srate\t\t{rate}"]
    return "\n".join(lines) + "\n"


def module_loads(sinks=None, stand_in=False):
    """the pactl lines that create the sinks, in an order a person can read and rerun.

    the agent needs two. the stand-in far end needs the other two, and only the self-test asks for them.
    """
    names = dict(SINKS)
    names.update(sinks or {})
    keys = ("say", "hear") + (("far_say", "far_hear") if stand_in else ())
    return [f"pactl load-module module-null-sink sink_name={names[k]}" for k in keys]


def no_loop(sinks=None):
    """the invariant, as a function: no output sink is also read as an input by the same side."""
    names = dict(SINKS)
    names.update(sinks or {})
    return names["say"] != names["hear"] and names["far_say"] != names["far_hear"]


def env(runtime=None, server=None):
    """the environment a pump subprocess needs when pulseaudio is not the session's own."""
    out = dict(os.environ)
    if runtime:
        out["XDG_RUNTIME_DIR"] = str(runtime)
        out["PULSE_RUNTIME_PATH"] = str(runtime)
    if server:
        out["PULSE_SERVER"] = server
    return out


def speak(wav, sink=None, environment=None, runner=subprocess.run, timeout=120):
    """the mouth: play a wav into the sink baresip reads as its microphone.

    the call is what carries it, so this returns when the file has been handed over, not when the far
    end has heard it. a wav the call cannot carry is refused by name rather than played as noise.
    """
    problem = wav_problem(wav)
    if problem:
        return {"ok": False, "why": problem}
    sink = sink or SINKS["say"]
    done = runner(["paplay", f"--device={sink}", str(wav)], capture_output=True, text=True,
                  timeout=timeout, env=environment)
    return {"ok": done.returncode == 0, "sink": sink, "wav": str(wav), "stderr": (done.stderr or "").strip()}


def listen(path, seconds, sink=None, rate=48000, environment=None, popen=subprocess.Popen,
           sleep=time.sleep):
    """the ears: record what the call plays to the agent, for a stated number of seconds.

    the recorder is started first and stopped by this function, never left running, because a recorder
    that outlives its call fills a disk with silence.
    """
    sink = sink or SINKS["hear"]
    proc = popen(["parecord", f"--device={sink}.monitor", "--file-format=wav", "--channels=1",
                  f"--rate={rate}", str(path)], env=environment, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL)
    try:
        sleep(seconds)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    return {"ok": True, "sink": f"{sink}.monitor", "path": str(path), "seconds": seconds}


def wav_problem(path):
    try:
        with wave.open(str(path)) as handle:
            if handle.getsampwidth() != 2:
                return "the wav must be 16 bit pcm, which is what a g711 call is decoded to"
            if handle.getnframes() == 0:
                return "the wav is empty"
    except (OSError, EOFError, wave.Error) as error:
        return f"not a wav the pump can play: {error}"
    return None


def levels(path, window_s=0.1):
    """a recording, summarised so a test (or a person) can tell speech from silence without listening.

    returns the peak, the share of windows that carry signal, and the span they cover. a recording that
    is silent end to end is the commonest failure and looks identical to a working one in a file list.
    """
    import struct
    with wave.open(str(path)) as handle:
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
        channels = handle.getnchannels()
    samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
    if channels > 1:
        samples = samples[::channels]
    window = max(1, int(rate * window_s))
    peaks = [max((abs(x) for x in samples[i:i + window]), default=0) for i in range(0, len(samples), window)]
    threshold = max(200, (max(peaks) if peaks else 0) // 8)
    loud = [i for i, p in enumerate(peaks) if p > threshold]
    return {
        "frames": len(samples), "rate": rate,
        "peak": max((abs(x) for x in samples), default=0),
        "windows": len(peaks), "loud_windows": len(loud),
        "starts_s": round(loud[0] * window_s, 2) if loud else None,
        "ends_s": round((loud[-1] + 1) * window_s, 2) if loud else None,
        "silent": not loud,
    }


def tone_energy(path, frequency):
    """goertzel energy at one frequency: the cheap way to say 'this is the tone, not noise'."""
    import math
    import struct
    with wave.open(str(path)) as handle:
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
        channels = handle.getnchannels()
    samples = struct.unpack("<%dh" % (len(frames) // 2), frames)
    if channels > 1:
        samples = samples[::channels]
    k = 2 * math.cos(2 * math.pi * frequency / rate)
    a = b = 0.0
    for x in samples:
        a, b = x + k * a - b, a
    return (a * a + b * b - k * a * b) / max(1, len(samples))


def plan():
    """what a host has to do, in order, to give the agent ears and a mouth. nothing here is run."""
    return {
        "shipped": True,
        "what": ("the agent's voice goes into a null sink that baresip reads as its microphone, and the "
                 "far end's voice is recorded from the sink baresip plays into"),
        "tools": tools_present(),
        "sinks": dict(SINKS),
        "create": ["pactl load-module module-null-sink sink_name=agent_say",
                   "pactl load-module module-null-sink sink_name=agent_hear"],
        "baresip": baresip_audio(),
        "mouth": "paplay --device=agent_say <wav>",
        "ears": "parecord --device=agent_hear.monitor --file-format=wav <path>",
        "no_loop": no_loop(),
        "why_four_not_two": ("one sink used for both directions feeds the call's playback back into its "
                             "own microphone, which saturates the capture. each direction gets its own"),
        "not_included": ["a transcript: turning ears into text needs a speech model, and this repo ships none",
                         "a livekit room: joining the call to a room is the bridge, still not shipped"],
        "measured": MEASURED,
    }
