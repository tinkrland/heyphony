#!/usr/bin/env node
"use strict";

/*
 * run: one verb, one answer, parsed.
 *
 * every heyphony command that answers rather than acts prints json on stdout, and this turns that into
 * an object instead of a string. when the text is not json the text is kept, because a verb that
 * refuses with a sentence is still refusing correctly and swallowing it would be worse than parsing it.
 */

const { captured } = require("./python");

function firstJson(text) {
  const body = String(text || "");
  try {
    return { json: JSON.parse(body), rest: "" };
  } catch {
    /* not the whole body, so look for the document inside it */
  }
  for (let start = body.indexOf("{"); start !== -1; start = body.indexOf("{", start + 1)) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = start; i < body.length; i += 1) {
      const ch = body[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === "\\") escaped = true;
        else if (ch === '"') inString = false;
        continue;
      }
      if (ch === '"') inString = true;
      else if (ch === "{") depth += 1;
      else if (ch === "}") {
        depth -= 1;
        if (depth === 0) {
          try {
            return { json: JSON.parse(body.slice(start, i + 1)), rest: body.slice(0, start) };
          } catch {
            break;
          }
        }
      }
    }
  }
  return { json: null, rest: body };
}

function run(args, options) {
  const opts = options || {};
  const answer = captured(args, opts);
  const parsed = firstJson(answer.stdout);
  const ok = answer.code === 0 && !answer.spawn_error;
  return {
    ok,
    code: answer.code,
    argv: args,
    json: parsed.json,
    text: answer.stdout.trim(),
    stderr: answer.stderr.trim(),
    spawn_error: answer.spawn_error || null,
    why: !ok
      ? (answer.spawn_error ? answer.stderr.trim() : answer.stderr.trim() || `heyphony ${args.join(" ")} exited ${answer.code}`)
      : null,
  };
}

module.exports = { run, firstJson };
