#!/usr/bin/env node
"use strict";

/*
 * the mcp server, spoken to over a pipe, because that is the only way a client will speak to it.
 *
 * the assertions are the contract rather than the implementation: it answers initialize with a
 * protocol version and its own version, it lists tools that are schemas, a read tool runs and returns
 * json, an unknown tool is an error and not a crash, and a spending tool with a shut gate returns a
 * draft that says which environment variable was closed.
 */

const assert = require("assert");
const path = require("path");
const { spawn } = require("child_process");

const server = path.join(__dirname, "..", "bin", "heyphony-mcp.js");
const pkg = require("../package.json");

function session(messages, options) {
  const opts = options || {};
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [server], {
      stdio: ["pipe", "pipe", "pipe"],
      env: Object.assign({}, process.env, opts.env || {}),
    });
    let out = "";
    let err = "";
    child.stdout.on("data", (chunk) => { out += chunk; });
    child.stderr.on("data", (chunk) => { err += chunk; });
    child.on("error", reject);
    for (const message of messages) child.stdin.write(`${JSON.stringify(message)}\n`);
    child.stdin.end();
    child.on("exit", (code) => {
      const lines = out.split("\n").filter((line) => line.trim());
      resolve({ code, lines, err, replies: lines.map((line) => JSON.parse(line)) });
    });
  });
}

function tool(name, args, env) {
  return session([
    { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "1" } } },
    { jsonrpc: "2.0", id: 2, method: "tools/call", params: { name, arguments: args || {} } },
  ], { env }).then((answer) => answer.replies[1].result);
}

function body(result) {
  return JSON.parse(result.content[0].text);
}

async function main() {
  const hello = await session([
    { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "1" } } },
    { jsonrpc: "2.0", id: 2, method: "tools/list", params: {} },
    { jsonrpc: "2.0", id: 3, method: "ping" },
    { jsonrpc: "2.0", id: 4, method: "no/such/method" },
  ]);
  const [initialized, listed, pinged, missing] = hello.replies;

  assert.strictEqual(initialized.result.protocolVersion, "2025-06-18", "it should answer the version it was asked for");
  assert.strictEqual(initialized.result.serverInfo.version, pkg.version, "the server version is the package version");
  assert.ok(initialized.result.capabilities.tools, "tools is the capability it has");

  const names = listed.result.tools.map((entry) => entry.name);
  assert.deepStrictEqual(names.slice(0, 2), ["heyphony_status", "heyphony_doctor"]);
  for (const entry of listed.result.tools) {
    assert.strictEqual(entry.inputSchema.type, "object", `${entry.name} takes an object`);
    assert.ok(entry.description && entry.description.length > 20, `${entry.name} explains itself`);
    assert.strictEqual(entry.annotations.destructiveHint, false);
  }
  const spending = listed.result.tools.filter((entry) => !entry.annotations.readOnlyHint).map((entry) => entry.name);
  assert.deepStrictEqual(spending, ["heyphony_send_text", "heyphony_group_say", "heyphony_voicemail"],
    "only the three verbs that reach outside this machine are marked as doing so");

  assert.deepStrictEqual(pinged.result, {}, "ping answers empty");
  assert.strictEqual(missing.error.code, -32601, "an unknown method is an error, not a crash");

  const status = await tool("heyphony_status");
  assert.strictEqual(status.isError, false, "status answers");
  assert.ok(status.structuredContent && typeof status.structuredContent === "object", "status has structure");
  assert.strictEqual(status.structuredContent.command, "heyphony status");

  const unknown = await tool("heyphony_teleport");
  assert.strictEqual(unknown.isError, true);
  assert.match(unknown.content[0].text, /no such tool/);

  const empty = await tool("heyphony_send_text", { to: "+15551234567" });
  assert.strictEqual(empty.isError, true);
  assert.match(empty.content[0].text, /missing text/);

  const shutEnv = Object.assign({}, process.env);
  delete shutEnv.HEYPHONY_SEND;
  const drafted = await tool("heyphony_send_text",
    { to: "+15551234567", text: "hello from a tool call" }, { HEYPHONY_SEND: "" });
  const draftBody = body(drafted);
  assert.strictEqual(draftBody.gate.closed, true, "a shut gate is reported, not hidden");
  assert.strictEqual(draftBody.gate.drafted, true);
  assert.match(draftBody.gate.means, /HEYPHONY_SEND=allowed/);
  assert.doesNotMatch(draftBody.command, /--send/, "the flag is absent when the gate is shut");

  console.log("mcp: " + [
    "initialize", "tools/list", "ping", "unknown method", "status", "unknown tool",
    "missing argument", "shut gate drafts", "spending tools are flagged",
  ].length + " checks pass, " + names.length + " tools");
}

main().catch((error) => {
  console.error(`mcp: ${error.message}`);
  process.exit(1);
});
