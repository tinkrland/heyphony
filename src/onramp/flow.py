"""getters: rails a provisioned number can open, as data instead of prose.

a getter is not a lane. a lane lives in the comms branch and owns its own carrier,
gate and state. a getter is the one recipe heyphony can execute *because* it already
holds a number: signal is the first, and it is first for a boring reason - it wants a
phone or an sms, and this package is the thing that has both.

so the knowledge stays data (getters/<name>.json), the execution is opt-in (`get --run`,
and even then the qr scan is left to a human), and nothing here imports the umbrella.
"""
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
DIR = HERE   # recipes sit beside this file, one json per rail


def available():
    if not DIR.is_dir():
        return {}
    return {p.stem: json.loads(p.read_text()) for p in sorted(DIR.glob("*.json"))}


def default_path(recipe):
    return next(iter(recipe["paths"]))


def plan(name, path=None, env=None):
    """what would happen, resolved against the number this host actually holds."""
    env = env if env is not None else os.environ
    recipes = available()
    if name not in recipes:
        return {"gettable": False, "why": f"no getter named {name}",
                "known": sorted(recipes)}
    recipe = recipes[name]
    path = path or default_path(recipe)
    if path not in recipe["paths"]:
        return {"gettable": False, "why": f"{name} has no path called {path}",
                "paths": sorted(recipe["paths"])}
    chosen = recipe["paths"][path]
    missing = []
    if chosen.get("needs_number") and not env.get(chosen.get("gate_env", "HEYPHONY_SIP_DID")):
        missing.append(chosen.get("gate_env", "HEYPHONY_SIP_DID"))
    steps = chosen.get("steps") or []
    if steps and any(s.get("human") for s in steps):
        pass  # a human act inside the path, not a blocker for the plan
    return {
        "getter": name, "path": path, "what": chosen["what"],
        "gettable": not missing, "missing": missing,
        "why_preferred": chosen.get("why_preferred") or chosen.get("why_risky"),
        "install": recipe["install"], "steps": steps, "flow": recipe.get("flow"),
        "env": recipe["env"], "verify": recipe["verify"],
        "refused": recipe["refused"], "state": recipe["state"],
        "needs_a_human": [s["about"] for s in recipe["install"] + steps if s.get("human")],
        "paths": sorted(recipe["paths"]),
        "why_heyphony": recipe["why"],
    }


def run(name, path="link-device", env=None, dry=True):
    """execute the install steps. dry by default, because installing is a real change."""
    plan_out = plan(name, path, env)
    if not plan_out["gettable"]:
        return plan_out
    results = []
    for step in plan_out["install"]:
        if step.get("human") or dry:
            results.append({"cmd": step["cmd"], "executed": False, "why": "dry run" if not step.get("human") else "human act"})
            continue
        proc = subprocess.run(step["cmd"], shell=True, capture_output=True, text=True)
        results.append({"cmd": step["cmd"], "executed": True, "code": proc.returncode,
                        "out": (proc.stdout or "").strip()[-400:], "err": (proc.stderr or "").strip()[-400:]})
    nxt = plan_out["steps"][0]["about"] if plan_out.get("steps") else "the install steps above"
    return {**plan_out, "ran": results, "dry": dry, "next": nxt}
