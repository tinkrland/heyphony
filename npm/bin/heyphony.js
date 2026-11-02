#!/usr/bin/env node
"use strict";

/*
 * the only node in this package.
 *
 * heyphony is python: the sip config it writes, the inbox it reads and the webhook it catches are
 * python files. node is here for one reason, which is that `npm i -g heyphony` and `npx heyphony`
 * are the shortest path from "an agent has a machine" to "an agent has a number", and that path is
 * worth one shim. this file finds a python, points it at the python tree shipped beside it, and
 * gets out of the way. it does not parse heyphony's output and it never answers for it.
 */

const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const pkgDir = path.resolve(__dirname, "..");
const pythonTree = path.join(pkgDir, "python");

function version() {
  try {
    const text = fs.readFileSync(path.join(pythonTree, "src", "__init__.py"), "utf8");
    return (text.match(/__version__\s*=\s*["']([^"']+)["']/) || [])[1] || "unknown";
  } catch {
    return "unknown";
  }
}

function candidates() {
  const list = [];
  if (process.env.HEYPHONY_PYTHON) list.push({ cmd: process.env.HEYPHONY_PYTHON, args: [] });
  if (process.platform === "win32") list.push({ cmd: "py", args: ["-3"] });
  list.push({ cmd: "python3", args: [] }, { cmd: "python", args: [] });
  return list;
}

function trySpawn(candidate, argv, index) {
  const env = Object.assign({}, process.env, {
    PYTHONPATH: [pythonTree, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    // the tree has no .gitignore to hide a stray __pycache__, so the shim does not write one
    PYTHONDONTWRITEBYTECODE: "1",
  });

  const child = spawn(candidate.cmd, [...candidate.args, ...argv], { stdio: "inherit", env });

  child.on("error", (error) => {
    if (error.code === "ENOENT") {
      const next = candidates()[index + 1];
      if (next) return trySpawn(next, argv, index + 1);
      console.error(
        [
          "heyphony needs python 3.8 or newer and could not find one.",
          "",
          "  macOS    brew install python3",
          "  debian   sudo apt install python3",
          "  windows  winget install Python.Python.3.12   (then re-run inside a new shell)",
          "",
          "already have it under another name? set HEYPHONY_PYTHON=/path/to/python3",
          "this package ships the code itself; it is the interpreter that lives on your machine.",
        ].join("\n")
      );
      process.exit(127);
    }
    console.error(`heyphony: could not start ${candidate.cmd}: ${error.message}`);
    process.exit(126);
  });

  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => child.kill(signal));
  }

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code === null ? 1 : code);
  });
}

const argv = process.argv.slice(2);

if (argv[0] === "--version" || argv[0] === "-v") {
  console.log(version());
  process.exit(0);
}

if (!fs.existsSync(path.join(pythonTree, "src", "runner", "cli.py"))) {
  console.error(
    [
      "heyphony: the python code is not in this copy of the package.",
      "",
      "from a clone of the repo, build it first:   node npm/scripts/bundle.js",
      "from npm, reinstall:                        npm i -g heyphony@latest",
    ].join("\n")
  );
  process.exit(1);
}

trySpawn(candidates()[0], ["-m", "src.runner.cli", ...argv], 0);
