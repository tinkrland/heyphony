"""the folder list, discovered rather than hardcoded.

adding a lane is adding a folder with a `<folder>_lane.py` that exposes LANE. nothing
central needs editing, and a folder with no module is not silently counted as a lane.
"""
import importlib.util
from pathlib import Path

from comms import envelope

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"comms", "heyphony", "bin", "tests", "docs", "inbox", "__pycache__"}


def _load(folder):
    path = ROOT / folder / f"{folder}_lane.py"
    spec = importlib.util.spec_from_file_location(f"{folder}_lane", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def folders():
    return sorted(p.name for p in ROOT.iterdir()
                  if p.is_dir() and p.name not in SKIP and (p / f"{p.name}_lane.py").is_file())


def lanes():
    return {name: _load(name).LANE for name in folders()}


def states(env=None):
    return {name: envelope.state_for(spec, env) for name, spec in lanes().items()}


def reachable(env=None):
    return [name for name, st in states(env).items() if st["state"] != "closed"]
