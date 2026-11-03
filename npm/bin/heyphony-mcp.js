#!/usr/bin/env node
"use strict";

/*
 * an mcp server with no dependencies, because the alternative is a dependency tree for a transport.
 *
 * what it is: json-rpc on stdin and stdout, one message per line, and each tool is a heyphony command
 * whose json comes back as the tool result. what it is not: a second implementation of anything. the
 * gates that decide whether a text leaves live in the python (a --send flag *and* HEYPHONY_SEND=allowed,
 * a --send flag *and* HEYPHONY_CALL=allowed for dialling), and this server never closes one of them on
 * the caller's behalf. when the gate is shut the tool still runs, still answers, and reports the draft
 * with the gate named, which is what the cli would have printed in a terminal.
 *
 * anything written to stdout that is not a json-rpc message breaks the client, so diagnostics go to
 * stderr and only the protocol goes out on fd 1.
 */

const readline = require("readline");
const { version, missingTree, MISSING_TREE } = require("../lib/python");
const { run } = require("../lib/run");

const PROTOCOL = "2025-06-18";
const SEND_GATE = "HEYPHONY_SEND";
const CALL_GATE = "HEYPHONY_CALL";

const str = (description) => ({ type: "string", description });
const int = (description) => ({ type: "integer", description });
const bool = (description) => ({ type: "boolean", description });

const TOOLS = [
  {
    name: "heyphony_status",
    title: "Heyphony status",
    description:
      "What this machine's number can actually do: which rail is set up, which env vars it still needs, " +
      "and whether the inbox is reachable. Read-only, and always the safest first call.",
    input: {},
    args: () => ["status"],
  },
  {
    name: "heyphony_doctor",
    title: "Heyphony doctor",
    description: "The preflight for the host itself: python, the sip config, the data directory, the hooks.",
    input: {},
    args: () => ["doctor"],
  },
  {
    name: "heyphony_open_messages",
    title: "Read messages",
    description:
      "The inbox as json: who wrote, when, the body, and any group a sender belongs to. This reads; it " +
      "does not mark anything read unless asked.",
    input: {
      unread: bool("only the rows not yet marked read"),
      since_days: int("only rows newer than this many days"),
      limit: int("how many rows, newest first"),
    },
    args: (a) => ["open", "messages",
      ...(a.unread ? ["--unread"] : []),
      ...(a.since_days !== undefined ? ["--since", String(a.since_days)] : []),
      ...(a.limit !== undefined ? ["--limit", String(a.limit)] : [])],
  },
  {
    name: "heyphony_open_calls",
    title: "Read calls",
    description: "The call log as json, newest first.",
    input: { limit: int("how many rows"), missed: bool("only the unanswered ones") },
    args: (a) => ["open", "calls",
      ...(a.limit !== undefined ? ["--limit", String(a.limit)] : []),
      ...(a.missed ? ["--missed"] : [])],
  },
  {
    name: "heyphony_open_voicemail",
    title: "Read voicemail",
    description: "The voicemail log as json, with the transcript the carrier or the rail produced.",
    input: { limit: int("how many rows") },
    args: (a) => ["open", "voicemail", ...(a.limit !== undefined ? ["--limit", String(a.limit)] : [])],
  },
  {
    name: "heyphony_send_paths",
    title: "Which providers can send",
    description:
      "Every provider and what its outbound story is: wired, gateway not wired, or no outbound claim. " +
      "Read this before promising a send on a provider nobody has checked.",
    input: {},
    args: () => ["send", "--paths"],
  },
  {
    name: "heyphony_send_text",
    title: "Send one text",
    description:
      "One recipient, one body, through the rail. DRAFTS unless " + SEND_GATE + "=allowed is set in the " +
      "server's environment: the draft comes back with the gate named rather than being sent. A list of " +
      "recipients is refused on purpose, and 1600 characters is the ceiling.",
    input: {
      to: str("one recipient in e164, for example +15551234567"),
      text: str("the body, up to 1600 characters"),
      from: str("the did the provider holds; defaults to HEYPHONY_SIP_DID"),
      provider: str("the provider to send through; defaults to HEYPHONY_SIP_PROVIDER then voip.ms"),
    },
    required: ["to", "text"],
    gate: SEND_GATE,
    args: (a) => ["send", "--to", a.to, "--text", a.text,
      ...(a.from ? ["--from", a.from] : []),
      ...(a.provider ? ["--provider", a.provider] : [])],
  },
  {
    name: "heyphony_group_list",
    title: "List groups",
    description: "The named small conversations this number holds, with their members.",
    input: {},
    args: () => ["group", "list"],
  },
  {
    name: "heyphony_group_show",
    title: "Show a group",
    description: "One group: its members, its messages, and what its members can actually see.",
    input: { group: str("the group id or its name") },
    required: ["group"],
    args: (a) => ["group", "show", "--group", a.group],
  },
  {
    name: "heyphony_group_say",
    title: "Say it to a group",
    description:
      "One message to every member of a named group, one recipient at a time through the same rail and " +
      "the same gates. DRAFTS unless " + SEND_GATE + "=allowed.",
    input: { group: str("the group id or its name"), text: str("the body") },
    required: ["group", "text"],
    gate: SEND_GATE,
    args: (a) => ["group", "say", "--group", a.group, "--text", a.text],
  },
  {
    name: "heyphony_voicemail",
    title: "Leave a voicemail",
    description:
      "Place one call and speak a message into it. DRAFTS unless " + CALL_GATE + "=allowed: there is no " +
      "answering-machine detection on this rail, so it waits a fixed time and then talks.",
    input: {
      to: str("the number to call in e164"),
      message: str("what to say when it is answered"),
      wait: int("seconds after answer before speaking"),
    },
    required: ["to", "message"],
    gate: CALL_GATE,
    args: (a) => ["voicemail", "--to", a.to, "--message", a.message,
      ...(a.wait !== undefined ? ["--wait", String(a.wait)] : [])],
  },
  {
    name: "heyphony_hooks",
    title: "Inbound hook",
    description:
      "The url and the provider setting that make texts arrive at this machine, for one provider. " +
      "--apply is not exposed here: pointing a carrier at a machine is a decision, not a tool call.",
    input: { provider: str("the provider id, for example voip.ms") },
    args: (a) => ["hooks", ...(a.provider ? [a.provider] : [])],
  },
];

const BY_NAME = new Map(TOOLS.map((tool) => [tool.name, tool]));

function schema(tool) {
  return {
    type: "object",
    properties: tool.input || {},
    ...(tool.required ? { required: tool.required } : {}),
    additionalProperties: false,
  };
}

function listTools() {
  return {
    tools: TOOLS.map((tool) => ({
      name: tool.name,
      title: tool.title,
      description: tool.description,
      inputSchema: schema(tool),
      annotations: {
        title: tool.title,
        readOnlyHint: !tool.gate,
        // a send is outside this machine, and a draft is not. the hint follows the gate, not the tool
        openWorldHint: Boolean(tool.gate),
        destructiveHint: false,
        idempotentHint: false,
      },
    })),
  };
}

function gateOpen(name) {
  return String(process.env[name] || "").toLowerCase() === "allowed";
}

function callTool(name, args) {
  const tool = BY_NAME.get(name);
  if (!tool) {
    return { isError: true, content: [{ type: "text", text: `no such tool: ${name}. the server lists ${TOOLS.length}.` }] };
  }
  const input = args || {};
  const missing = (tool.required || []).filter((key) => input[key] === undefined || input[key] === null || input[key] === "");
  if (missing.length) {
    return { isError: true, content: [{ type: "text", text: `missing ${missing.join(", ")}: ${tool.name} needs ${missing.join(", ")}.` }] };
  }

  const argv = tool.args(input);
  const shut = Boolean(tool.gate) && !gateOpen(tool.gate);
  // the flag goes on only for a spending tool whose gate is open. a read tool never gets one, and a
  // shut gate means the flag is absent and the verb replies with the draft, as it would in a terminal
  const full = tool.gate && !shut ? [...argv, "--send"] : argv;
  const answer = run(full, { timeout: 90000 });

  const payload = {
    ok: answer.ok,
    command: ["heyphony", ...argv].join(" "),
    result: answer.json,
    text: answer.json ? undefined : answer.text || undefined,
    stderr: answer.stderr || undefined,
    gate: tool.gate
      ? (shut
        ? { closed: true, name: tool.gate, drafted: true,
            means: `nothing left this machine. ${tool.gate}=allowed in the server's environment is what closes it, and that is a decision for the human who started the server, not for a tool call.` }
        : { closed: false, name: tool.gate, drafted: false })
      : undefined,
    why: answer.why || undefined,
  };

  const clean = JSON.parse(JSON.stringify(payload));
  return {
    isError: !answer.ok,
    content: [{ type: "text", text: JSON.stringify(clean, null, 2) }],
    structuredContent: clean,
  };
}

function handle(message) {
  const { id, method, params } = message || {};
  const reply = (result) => ({ jsonrpc: "2.0", id, result });
  const fail = (code, message_, data) => ({ jsonrpc: "2.0", id, error: { code, message: message_, ...(data ? { data } : {}) } });

  if (method === "initialize") {
    const asked = params && params.protocolVersion;
    return reply({
      protocolVersion: typeof asked === "string" && asked ? asked : PROTOCOL,
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "heyphony", title: "heyphony: a number an agent can hold", version: version() },
      instructions:
        "heyphony gives an agent a phone number of its own: a sip did, an inbox that survives the machine " +
        "sleeping, and the rails a number unlocks. Start with heyphony_status. Sending tools draft unless " +
        `${SEND_GATE}=allowed is set in this server's environment, and the draft says so rather than failing.`,
    });
  }
  if (method === "ping") return reply({});
  if (method === "tools/list") return reply(listTools());
  if (method === "tools/call") {
    const name = params && params.name;
    return reply(callTool(name, params && params.arguments));
  }
  if (typeof method === "string" && method.startsWith("notifications/")) return null;
  return fail(-32601, `method not found: ${String(method)}`);
}

function write(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

if (missingTree()) {
  process.stderr.write(`${MISSING_TREE}\n`);
}

const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on("line", (line) => {
  const text = line.trim();
  if (!text) return;
  let message;
  try {
    message = JSON.parse(text);
  } catch (error) {
    write({ jsonrpc: "2.0", id: null, error: { code: -32700, message: `parse error: ${error.message}` } });
    return;
  }
  if (message && message.id === undefined && typeof message.method === "string") {
    // a notification: act on the ones that matter and stay silent on the rest
    return;
  }
  let answer;
  try {
    answer = handle(message);
  } catch (error) {
    answer = { jsonrpc: "2.0", id: message && message.id, error: { code: -32603, message: error.message } };
  }
  if (answer) write(answer);
});

process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT", () => process.exit(0));
