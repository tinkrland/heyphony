"""rig: a far end on this machine, so the agent's side of a call can be run without a carrier.

a real call needs a did, a registration and somebody answering. none of that is needed to find out
whether the audio path works, because baresip will call another baresip over loopback. this starts two:
the agent's, whose speaker and microphone are the two sinks the pump uses, and a stand-in far end that
auto answers and has the other two. it exists for the self-test and for anyone who wants to see the
pump work before they hold a number.

two facts that cost a failed run each, kept here because they look like the client's fault:

- **a sip port takes the next one with it.** baresip binds tls on `sip_listen` plus one, so a second
  instance on the adjacent port dies with "address already in use" before it reads its accounts. the two
  ports below are ten apart for that reason.
- **four sinks, not two.** see pump.py. one sink per direction per side is the only layout where no
  output can reach its own input.
"""
import os
import pathlib
import shutil
import subprocess
import time

from callheavy.src import pump

# the stand-in answers on its own after baresip's default auto answer delay, which is two seconds. a call
# placed at it is therefore established at 2.04s every time (measured over four cold starts), so a caller
# that listens for two seconds will miss the answer by 40 milliseconds. SETTLE leaves room for it.
ANSWER_DELAY_S = 2.0
SETTLE_S = 6.0

AGENT = {"sip": 5061, "ctrl": 4461, "user": "agent"}
FAR = {"sip": 5071, "ctrl": 4462, "user": "farend"}

MODULES = ("stdio.so", "g711.so", "account.so", "pulse.so", "menu.so", "ctrl_tcp.so")
MODULE_DIRS = ("/usr/lib/baresip/modules", "/usr/lib/x86_64-linux-gnu/baresip/modules",
               "/usr/local/lib/baresip/modules", "/opt/homebrew/lib/baresip/modules")


def module_path(exists=os.path.isdir):
    for candidate in MODULE_DIRS:
        if exists(candidate):
            return candidate
    return None


def config_text(side, sinks, modules_dir, rate=48000):
    """one baresip config. the speaker and microphone come from pump so the two cannot drift apart."""
    hear, say = sinks
    lines = [
        f"sip_listen\t\t127.0.0.1:{side['sip']}",
        "call_max_calls\t\t4",
        f"audio_player\t\tpulse,{hear}",
        f"audio_source\t\tpulse,{say}.monitor",
        f"audio_alert\t\tpulse,{hear}",
        f"ausrc_srate\t\t{rate}",
        f"auplay_srate\t\t{rate}",
        f"module_path\t\t{modules_dir}",
    ]
    lines += [f"module\t\t\t{name}" for name in MODULES]
    lines.append(f"ctrl_tcp_listen\t\t127.0.0.1:{side['ctrl']}")
    return "\n".join(lines) + "\n"


def account_text(side, auto_answer):
    flags = ";regint=0" + (";answermode=auto" if auto_answer else "")
    return f"<sip:{side['user']}@127.0.0.1:{side['sip']}>{flags}\n"


def ports_apart(a=AGENT, b=FAR):
    """true when neither instance's tls port (sip + 1) lands on the other's sip or tls port."""
    taken = {a["sip"], a["sip"] + 1}
    return not ({b["sip"], b["sip"] + 1} & taken)


def write(root):
    """write both configs under root and return where they went. nothing is started."""
    root = pathlib.Path(root)
    modules_dir = module_path() or MODULE_DIRS[0]
    agent_sinks = (pump.SINKS["hear"], pump.SINKS["say"])
    far_sinks = (pump.SINKS["far_hear"], pump.SINKS["far_say"])
    out = {}
    for name, side, sinks, auto in (("agent", AGENT, agent_sinks, False), ("far", FAR, far_sinks, True)):
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "config").write_text(config_text(side, sinks, modules_dir))
        (folder / "accounts").write_text(account_text(side, auto))
        out[name] = str(folder)
    return out


class Rig:
    """pulseaudio with four null sinks, and the two baresip instances. use as a context manager."""

    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        self.run = self.root / "run"
        self.procs = []
        self.handles = []
        self.server = None
        self.log = self.root / "log"

    def environment(self):
        return pump.env(runtime=self.run, server=f"unix:{self.run}/native")

    def missing(self):
        need = [t for t in ("pulseaudio", "baresip", "pactl", "paplay", "parecord") if not shutil.which(t)]
        if not module_path():
            need.append("baresip modules (pulse.so, ctrl_tcp.so, menu.so)")
        return need

    def start(self, settle=3.0):
        gone = self.missing()
        if gone:
            return {"ok": False, "missing": gone}
        self.run.mkdir(parents=True, exist_ok=True)
        self.log.mkdir(parents=True, exist_ok=True)
        os.chmod(self.run, 0o700)
        env = self.environment()
        # in the foreground, under Popen, and not `--daemonize=yes`: a daemon forks away from the process
        # that started it, so there is no handle to stop it by. seven of them were left running before this,
        # because `pactl exit` cannot stop a server that was started with --disallow-exit.
        self.server = subprocess.Popen(
            ["pulseaudio", "-n", "--exit-idle-time=-1", "--disallow-exit",
             f"--log-target=file:{self.log}/pulse.log",
             f"--load=module-native-protocol-unix socket={self.run}/native"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(30):
            if (self.run / "native").exists():
                break
            time.sleep(0.2)
        for line in pump.module_loads(stand_in=True):
            subprocess.run(line.split(), env=env, capture_output=True, text=True, timeout=15)
        paths = write(self.root)
        for name in ("agent", "far"):
            handle = open(self.log / f"baresip-{name}.log", "w")
            self.handles.append(handle)
            self.procs.append(subprocess.Popen(["baresip", "-f", paths[name]], env=env, stdout=handle,
                                               stderr=subprocess.STDOUT, start_new_session=True))
            time.sleep(settle)
        alive = [p.poll() is None for p in self.procs]
        return {"ok": all(alive), "alive": alive, "root": str(self.root), "agent_ctrl": AGENT["ctrl"],
                "far_uri": f"sip:{FAR['user']}@127.0.0.1:{FAR['sip']}"}

    def stop(self):
        for proc in self.procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        self.procs = []
        for handle in self.handles:
            handle.close()
        self.handles = []
        if self.server is not None:
            if self.server.poll() is None:
                self.server.terminate()
                try:
                    self.server.wait(timeout=5)
                except Exception:
                    self.server.kill()
                    self.server.wait(timeout=5)
            self.server = None

    def __enter__(self):
        self.started = self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False
