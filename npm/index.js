"use strict";

/*
 * the sdk is the cli with the parsing done.
 *
 * there is deliberately no second implementation here: a node host that wants heyphony's answers gets
 * the same json the command prints, from the same python, through the same gates. what it does not get
 * is a way around a gate, because the gates live in the python and this file only passes arguments.
 */

const { run } = require("./lib/run");
const { version, pythonTree, missingTree } = require("./lib/python");

const read = (args, options) => run(args, options);

module.exports = {
  version,
  pythonTree,
  missingTree,
  run,
  status: (options) => read(["status"], options),
  doctor: (options) => read(["doctor"], options),
  open: (what, options) => read(["open", what || "all"], options),
  messages: (options) => read(["open", "messages"], options),
  calls: (options) => read(["open", "calls"], options),
  voicemails: (options) => read(["open", "voicemail"], options),
  sendPaths: (options) => read(["send", "--paths"], options),
  // `send` gates itself: without HEYPHONY_SEND=allowed this returns the draft, exactly as the cli does
  sendText: ({ to, text, from, provider, send }, options) =>
    read(["send", "--to", to, "--text", text, ...(from ? ["--from", from] : []),
      ...(provider ? ["--provider", provider] : []), ...(send ? ["--send"] : [])], options),
  groups: (options) => read(["group", "list"], options),
  groupShow: (group, options) => read(["group", "show", "--group", group], options),
};
