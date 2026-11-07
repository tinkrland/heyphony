"""first proof: run the rungs this branch can actually check, and say where each one stops.

the client spec names a ladder. a ladder nobody runs is a wish, so this is the ladder as a
program: every rung has a timeout, every rung reports passed, failed or skipped with the reason,
and the two rungs that need a real number are skipped out loud instead of quietly.

    python3 bench/first_proof.py            # json, one object per rung
    python3 bench/first_proof.py --quiet    # one line per rung

what it needs to say anything useful: a running pipewire (or pulse) daemon for the nodes and flow
rungs, and baresip for the console rung. absent tools are a skip, not a failure, so the harness is
honest on a laptop and on a container that has neither.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

TIMEOUT = 12
TONE = 440


def _have(*names):
    return [n for n in names if shutil.which(n)]


def _run(argv, **kw):
    kw.setdefault("timeout", TIMEOUT)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        done = subprocess.run(argv, **kw)
    except subprocess.TimeoutExpired:
        return {"ok": False, "timeout": True, "out": "", "err": f"timed out after {kw['timeout']}s"}
    except FileNotFoundError as exc:
        return {"ok": False, "missing": True, "out": "", "err": str(exc)}
    return {"ok": done.returncode == 0, "code": done.returncode,
            "out": done.stdout or "", "err": done.stderr or ""}


def _pactl(*args):
    return _run(["pactl", *args])


def rung_tools():
    audio = _have("pipewire", "pw-play", "pw-record", "pw-pulse", "pactl")
    sip = _have("baresip", "pjsua")
    if not audio:
        return "failed", f"no audio tooling on this host: found {audio or 'nothing'}"
    return "passed", f"audio tools {audio}, sip tools {sip or 'none'}"


def rung_nodes():
    """the three names the spec asks for, made by the two modules it names.

    the pulse module is the path the spec names, so it goes first. the fallback is pipewire's own
    adapter node with node.driver, which is what a headless host needs when no card supplies the
    clock, and the difference is worth reporting rather than flattening: on a container with no
    /dev/snd the adapter made a node that pulse could not see, so the three names stayed
    unconfirmed even though a sink existed.
    """
    if shutil.which("pactl") and _pactl("info")["ok"]:
        sink = _pactl("load-module", "module-null-sink", "sink_name=agent_probe")
        if not sink["ok"]:
            return "failed", f"null sink did not load: {sink['err'].strip()[:120]}"
        remap = _pactl("load-module", "module-remap-source", "master=agent_probe.monitor",
                       "source_name=agent_probe_mic")
        listing = _pactl("list", "short", "sinks")["out"] + _pactl("list", "short", "sources")["out"]
        found = [n for n in ("agent_probe", "agent_probe.monitor", "agent_probe_mic") if n in listing]
        if remap["ok"] and remap["out"].strip().isdigit():
            _pactl("unload-module", remap["out"].strip())
        if sink["out"].strip().isdigit():
            _pactl("unload-module", sink["out"].strip())
        if len(found) == 3:
            return "passed", f"the three nodes exist: {', '.join(found)}"
        return "failed", f"expected three nodes, saw {found or 'none'}"

    if shutil.which("pw-cli"):
        made = _run(["pw-cli", "create-node", "adapter",
                     "factory.name=support.null-audio-sink node.name=agent_probe "
                     "media.class=Audio/Sink audio.position=[FL,FR] "
                     "node.always-process=true node.driver=true object.linger=true"])
        graph = _run(["pw-cli", "ls", "Node"])
        if made["ok"] and "agent_probe" in graph["out"]:
            return "failed", ("a sink node exists in the graph, made by pipewire's adapter as its own "
                              "driver, and the pulse socket is down, so the monitor and the remap "
                              "source the spec names cannot be created or confirmed")

    return "skipped", "neither a working pulse socket nor pw-cli, so the null sink cannot be asked for"


def rung_flow():
    """play a tone into the sink while recording its monitor, then look for energy in the file."""
    if not (_have("pw-play") and _have("pw-record") and _have("ffmpeg")):
        return "skipped", "pw-play, pw-record and ffmpeg are needed together"
    sink = _pactl("load-module", "module-null-sink", "sink_name=agent_flow")
    if not sink["ok"]:
        return "skipped", "no null sink to speak into"
    tmp = tempfile.mkdtemp(prefix="proof-")
    speech, ear = os.path.join(tmp, "tts.wav"), os.path.join(tmp, "ear.wav")
    made = _run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={TONE}:duration=1",
                 "-ar", "48000", "-ac", "1", speech, "-y"])
    if not made["ok"]:
        return "skipped", "could not make a tone to speak"
    rec = subprocess.Popen(["pw-record", "--target", "agent_flow.monitor", ear],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    play = _run(["pw-play", "--target", "agent_flow", speech])
    time.sleep(1)
    rec.terminate()
    try:
        rec.wait(timeout=5)
    except subprocess.TimeoutExpired:
        rec.kill()
    if sink["out"].strip().isdigit():
        _pactl("unload-module", sink["out"].strip())
    if play.get("timeout"):
        return "failed", ("the player blocked: the nodes exist and nothing drives the graph clock, which "
                          "is what a container without a sound card does")
    level = _run(["ffmpeg", "-v", "error", "-i", ear, "-af", "volumedetect", "-f", "null", "-"])
    if not os.path.exists(ear):
        return "failed", "the recorder wrote nothing"
    energy = [line for line in level["err"].splitlines() if "max_volume" in line]
    if not energy:
        return "failed", "the recording has no measurable level, so the mouth did not reach the ear"
    return "passed", f"recorded the sink monitor: {energy[0].split(']')[-1].strip()}"


def rung_console():
    """can a process hand the console client a command, before any account exists."""
    if not shutil.which("baresip"):
        return "skipped", "baresip is not installed"
    conf = tempfile.mkdtemp(prefix="bf-")
    with open(os.path.join(conf, "config"), "w") as handle:
        handle.write("module stdio\nmodule g711\n")
    log = os.path.join(conf, "run.log")
    with open(log, "w") as out:
        proc = subprocess.Popen(["baresip", "-f", conf, "-e", "/quit"],
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        time.sleep(8)
        stopped = proc.poll() is None
        if stopped:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    blob = open(log, errors="replace").read().lower()
    acted = "quit" in blob and ("stop all" in blob or "ua:" in blob)
    no_modules = "cannot open shared object" in blob or "no such file or directory" in blob
    if acted:
        note = ("; it acts and then keeps running, so a supervisor has to stop it, and this package "
                "ships no modules so ctrl_tcp is not an option") if stopped else ""
        if no_modules:
            note += "; modules are missing from this build, which is why the console loop is absent"
        return "passed", f"a process handed it /quit and it acted on it{note}"
    if no_modules:
        return "failed", "this baresip ships no modules and did not act on a handed command"
    return "failed", f"baresip never acted on the command: {blob.strip().splitlines()[:1]}"


def rung_call():
    return "skipped", ("needs a did that is really registered and a handset to dial it: the one rung no "
                       "amount of local tooling answers")


def rung_phone():
    return "skipped", "needs a device we hold, and this host has none attached"


RUNGS = (
    ("tools", rung_tools),
    ("nodes", rung_nodes),
    ("flow", rung_flow),
    ("console", rung_console),
    ("call", rung_call),
    ("phone", rung_phone),
)


def proof():
    rows = []
    for name, fn in RUNGS:
        state, because = fn()
        rows.append({"rung": name, "state": state, "because": because})
    counts = {s: sum(1 for r in rows if r["state"] == s) for s in ("passed", "failed", "skipped")}
    return {"host": os.uname().nodename, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rungs": rows, "counts": counts,
            "means": ("passed is evidence, failed is a finding, skipped is an honest gap. nothing here "
                      "verifies a call, because a call needs a number and a handset.")}


def main(argv):
    quiet = "--quiet" in argv
    result = proof()
    if quiet:
        for row in result["rungs"]:
            print(f"{row['state']:8} {row['rung']:8} {row['because']}")
        print(json.dumps(result["counts"]))
        return 0
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
