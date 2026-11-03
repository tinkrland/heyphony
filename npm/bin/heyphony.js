#!/usr/bin/env node
"use strict";

/*
 * the terminal adapter.
 *
 * heyphony is python: the sip config it writes, the inbox it reads and the webhook it catches are
 * python files. node is here for one reason, which is that `npm i -g heyphony` and `npx heyphony`
 * are the shortest path from "an agent has a machine" to "an agent has a number", and that path is
 * worth one shim. this file finds a python and hands the terminal over. it does not parse heyphony's
 * output and it never answers for it; the one thing it answers itself is --version, because asking
 * python for the version to decide whether python works is a longer trip to the same answer.
 *
 * where the python is lives in ../lib/python.js, because the mcp server needs the same answer and two
 * copies of a search path is how they drift.
 */

const { version, missingTree, MISSING_TREE, handed } = require("../lib/python");

const argv = process.argv.slice(2);

if (argv[0] === "--version" || argv[0] === "-v") {
  console.log(version());
  process.exit(0);
}

if (missingTree()) {
  console.error(MISSING_TREE);
  process.exit(1);
}

handed(argv);
