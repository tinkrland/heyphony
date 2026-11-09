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
const fs = require("fs");
const os = require("os");
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


  // the inbound policy: readable and checkable by an agent, never editable by one
  assert.ok(names.includes("heyphony_lookup") && names.includes("heyphony_allow_show") && names.includes("heyphony_allow_check"),
    "lookup, allow_show and allow_check are tools");
  assert.deepStrictEqual(names.filter((n) => /allow/.test(n)).sort(), ["heyphony_allow_check", "heyphony_allow_show"],
    "there is no tool that edits the policy: widening who can text the agent is a human decision");
  for (const n of ["heyphony_lookup", "heyphony_allow_show", "heyphony_allow_check"]) {
    assert.strictEqual(listed.result.tools.find((e) => e.name === n).annotations.readOnlyHint, true, `${n} only reads`);
  }

  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "heyphony-allow-"));
  const policyEnv = { HEYPHONY_ALLOW: path.join(scratch, "allow.json"), XDG_DATA_HOME: path.join(scratch, "data") };
  try {
    const shut = await tool("heyphony_allow_check", { sender: "+447700900123" }, policyEnv);
    assert.strictEqual(shut.isError, false, "a refused sender is an answer, not a failure");
    assert.strictEqual(body(shut).result.allowed, false);
    assert.strictEqual(body(shut).result.why, "not-on-the-list", "the default policy admits nobody");
    assert.strictEqual(body(shut).ok, true, "ok and isError agree");

    fs.writeFileSync(policyEnv.HEYPHONY_ALLOW, JSON.stringify({ mode: "local", home: "GB" }));
    const open = await tool("heyphony_allow_check", { sender: "+44 7700 900123" }, policyEnv);
    assert.strictEqual(open.isError, false);
    assert.strictEqual(body(open).result.allowed, true, "a local number gets in when the home country matches");
    assert.strictEqual(body(open).result.region, "GB");

    const shown = body(await tool("heyphony_allow_show", {}, policyEnv));
    assert.strictEqual(shown.result.policy.mode, "local");
    assert.match(shown.result.means, /GB/);
  } finally {
    fs.rmSync(scratch, { recursive: true, force: true });
  }

  const looked = await tool("heyphony_lookup", { number: "+447700900123", mode: "line" });
  assert.strictEqual(looked.isError, false, "lookup answers");
  assert.ok(body(looked).result.line, "lookup returns the line reading");

  // the schema a tool advertises is held, not just printed
  for (const [label, name, args, pattern] of [
    ["a value outside the enum", "heyphony_lookup", { number: "+447700900123", mode: "zzz" }, /mode must be one of/],
    ["an argument nobody declared", "heyphony_allow_check", { sender: "+447700900123", extra: "x" }, /unknown argument extra/],
    ["the wrong type", "heyphony_allow_check", { sender: 12345 }, /sender must be a string/],
    ["a non-object", "heyphony_status", [1, 2], /arguments must be an object/],
  ]) {
    const refused = await tool(name, args);
    assert.strictEqual(refused.isError, true, `${label} is refused`);
    assert.match(refused.content[0].text, pattern, `${label} says why`);
  }


  // the sdk is the other adapter over the same verbs, and it must agree with the server about what a no is
  const sdk = require("..");
  assert.ok(!("allowSet" in sdk) && !("setAllow" in sdk) && !("allowMode" in sdk), "the sdk has no wrapper that edits the policy");
  const scratch2 = fs.mkdtempSync(path.join(os.tmpdir(), "heyphony-sdk-"));
  const savedAllow = process.env.HEYPHONY_ALLOW, savedData = process.env.XDG_DATA_HOME;
  process.env.HEYPHONY_ALLOW = path.join(scratch2, "allow.json");
  process.env.XDG_DATA_HOME = path.join(scratch2, "data");
  try {
    const no = sdk.allowCheck("+447700900123");
    assert.strictEqual(no.code, 1, "the verb exits 1 for a sender it refuses");
    assert.strictEqual(no.ok, true, "the sdk reports that no as an answer");
    assert.strictEqual(no.json.allowed, false);
    const plain = sdk.run(["allow", "check", "+447700900123"]);
    assert.strictEqual(plain.ok, false, "naming the exit code is opt in: a plain run still sees exit 1 as not ok");
    assert.strictEqual(sdk.allow().json.policy.mode, "list", "the default policy is the closed one");
    assert.ok(sdk.lookup("+447700900123", { mode: "line" }).json.line, "the sdk reads a number");
    const crash = sdk.run(["allow", "nonsense"], { answers: [0, 1, 2] });
    assert.strictEqual(crash.ok, false, "naming exit codes cannot turn a verb that printed nothing into an answer");
  } finally {
    if (savedAllow === undefined) delete process.env.HEYPHONY_ALLOW; else process.env.HEYPHONY_ALLOW = savedAllow;
    if (savedData === undefined) delete process.env.XDG_DATA_HOME; else process.env.XDG_DATA_HOME = savedData;
    fs.rmSync(scratch2, { recursive: true, force: true });
  }

  console.log("mcp: " + [
    "initialize", "tools/list", "ping", "unknown method", "status", "unknown tool",
    "missing argument", "shut gate drafts", "spending tools are flagged",
    "no tool edits the policy", "a refusal is an answer", "a local sender gets in", "the policy reads back",
    "lookup answers", "an undeclared enum value is refused", "an undeclared argument is refused",
    "the wrong type is refused", "a non-object is refused",
    "the sdk has no edit wrapper", "the sdk reports a no as an answer", "a plain run still sees exit 1 as not ok",
    "a named exit code cannot turn a crash into an answer",
  ].length + " checks pass, " + names.length + " tools");
}

main().catch((error) => {
  console.error(`mcp: ${error.message}`);
  process.exit(1);
});
