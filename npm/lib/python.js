#!/usr/bin/env node
"use strict";

/*
 * where the python is, and how to start it.
 *
 * heyphony is python. node is here because `npm i -g heyphony` is the shortest path from "an agent has
 * a machine" to "an agent has a number", and because an mcp client speaks json over stdio while the
 * cli speaks json on stdout. both of those are adapters, not implementations, so the discovery lives
 * in one file and neither caller is allowed its own copy of it.
 */

const { spawn, spawnSync } = require("child_process");
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

function env() {
  return Object.assign({}, process.env, {
    PYTHONPATH: [pythonTree, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    // the tree has no .gitignore to hide a stray __pycache__, so nothing here writes one
    PYTHONDONTWRITEBYTECODE: "1",
  });
}

function argvFor(args) {
  return ["-m", "src.runner.cli", ...args];
}

function missingTree() {
  return !fs.existsSync(path.join(pythonTree, "src", "runner", "cli.py"));
}

const MISSING_TREE = [
  "heyphony: the python code is not in this copy of the package.",
  "",
  "from a clone of the repo, build it first:   node npm/scripts/bundle.js",
  "from npm, reinstall:                        npm i -g heyphony@latest",
].join("\n");

const NO_PYTHON = [
  "heyphony needs python 3.8 or newer and could not find one.",
  "",
  "  macOS    brew install python3",
  "  debian   sudo apt install python3",
  "  windows  winget install Python.Python.3.12   (then re-run inside a new shell)",
  "",
  "already have it under another name? set HEYPHONY_PYTHON=/path/to/python3",
  "this package ships the code itself; it is the interpreter that lives on your machine.",
].join("\n");

/* hand the terminal over: the cli owns stdin, stdout and the exit code, and this function's job is
 * to get out of the way without swallowing a ctrl-c on the way past. */
function handed(args) {
  const list = candidates();
  const attempt = (index) => {
    const candidate = list[index];
    const child = spawn(candidate.cmd, [...candidate.args, ...argvFor(args)], {
      stdio: "inherit",
      env: env(),
    });
    child.on("error", (error) => {
      if (error.code === "ENOENT" && list[index + 1]) return attempt(index + 1);
      console.error(error.code === "ENOENT" ? NO_PYTHON : `heyphony: could not start ${candidate.cmd}: ${error.message}`);
      process.exit(error.code === "ENOENT" ? 127 : 126);
    });
    for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
      process.on(signal, () => child.kill(signal));
    }
    child.on("exit", (code, signal) => {
      if (signal) return process.kill(process.pid, signal);
      process.exit(code === null ? 1 : code);
    });
  };
  attempt(0);
}

/* read what it printed: same discovery, pipes instead of the terminal, and a timeout so a client
 * that asked for the inbox cannot hang on a python that is waiting for something. */
function captured(args, options) {
  const opts = options || {};
  for (const candidate of candidates()) {
    const answer = spawnSync(candidate.cmd, [...candidate.args, ...argvFor(args)], {
      encoding: "utf8",
      env: env(),
      timeout: opts.timeout || 60000,
      maxBuffer: 8 * 1024 * 1024,
      input: opts.input,
    });
    if (answer.error && answer.error.code === "ENOENT") continue;
    if (answer.error) {
      return { code: null, stdout: "", stderr: answer.error.message, spawn_error: answer.error.code || "spawn" };
    }
    return { code: answer.status, stdout: answer.stdout || "", stderr: answer.stderr || "" };
  }
  return { code: null, stdout: "", stderr: NO_PYTHON, spawn_error: "ENOENT" };
}

module.exports = { pkgDir, pythonTree, version, candidates, argvFor, handed, captured, missingTree, MISSING_TREE, NO_PYTHON };
