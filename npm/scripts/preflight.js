#!/usr/bin/env node
"use strict";

/*
 * preflight: everything that stands between this folder and a published package, checked in one run.
 *
 * the point is not to be clever, it is to be the thing a person runs before `npm publish` so that a
 * bad tarball is caught here rather than by somebody's `npx heyphony` ten minutes later. publish is
 * close to irreversible (a version number cannot be reused, and the unpublish window is short), so
 * the checks are ordered from cheapest to slowest and the last two are the ones that matter: does the
 * tarball install, and does the installed command actually answer.
 *
 * no dependencies. node and python3 are all this needs, which is the same pair the package needs.
 */

const { execFileSync, spawnSync } = require("child_process");
const fs = require("fs");
const https = require("https");
const os = require("os");
const path = require("path");

const pkgDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(pkgDir, "..");
const pkg = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8"));

const results = [];
const record = (name, ok, detail, blocking = true) => {
	results.push({ name, ok, detail: detail || "", blocking });
	return ok;
};

const run = (cmd, args, options = {}) => {
	const done = spawnSync(cmd, args, { encoding: "utf8", timeout: options.timeout || 240000,
		cwd: options.cwd || pkgDir, env: options.env || process.env });
	return { ok: done.status === 0, out: (done.stdout || "").trim(), err: (done.stderr || "").trim(),
		status: done.status };
};

const pythonVersion = (home) => {
	const which = process.env.HEYPHONY_PYTHON || "python3";
	const done = run(which, ["--version"], { env: { ...process.env, HOME: home || process.env.HOME } });
	if (!done.ok) return { ok: false, which, detail: `${which} not on PATH: the package cannot run without it` };
	const version = `${done.out} ${done.err}`.trim();
	const match = version.match(/(\d+)\.(\d+)/);
	if (!match) return { ok: false, which, detail: `could not read a version from ${version}` };
	const major = Number(match[1]),
		minor = Number(match[2]);
	const ok = major > 3 || (major === 3 && minor >= 8);
	return { ok, which, detail: `${version}${ok ? "" : " is too old, 3.8 is the floor"}` };
};

const readVersion = () => {
	const init = fs.readFileSync(path.join(repoRoot, "src", "__init__.py"), "utf8");
	const found = init.match(/__version__\s*=\s*["']([^"']+)["']/);
	return found ? found[1] : null;
};

const registry = (name) =>
	new Promise((resolve) => {
		const url = `https://registry.npmjs.org/${encodeURIComponent(name).replace("%40", "@").replace("%2F", "%2f")}`;
		const request = https.get(url, { timeout: 15000, headers: { accept: "application/json" } },
			(response) => {
				let body = "";
				response.on("data", (chunk) => { body += chunk; });
				response.on("end", () => {
					if (response.statusCode === 404) return resolve({ free: true, code: 404 });
					try {
						const data = JSON.parse(body);
						return resolve({ free: false, code: response.statusCode, latest: (data["dist-tags"] || {}).latest,
							owner: (data.maintainers || []).map((who) => who.name).join(", ") });
					} catch (error) {
						return resolve({ free: false, code: response.statusCode, latest: null, owner: null });
					}
				});
			});
		request.on("timeout", () => { request.destroy(); resolve({ free: null, code: null, timeout: true }); });
		request.on("error", (error) => resolve({ free: null, code: null, error: error.message }));
	});

const newestTarball = (dir) => {
	const found = fs.readdirSync(dir).filter((name) => name.endsWith(".tgz"));
	if (!found.length) return null;
	return path.join(dir, found.map((name) => ({ name, at: fs.statSync(path.join(dir, name)).mtimeMs }))
		.sort((a, b) => b.at - a.at)[0].name);
};

(async () => {
	console.log(`preflight: ${pkg.name}@${pkg.version}\n`);

	const nodeMajor = Number(process.versions.node.split(".")[0]);
	record("node version", nodeMajor >= 18, `v${process.versions.node}, engines wants ${pkg.engines.node}`, false);

	const python = pythonVersion();
	record("python3 on PATH", python.ok, python.detail);

	const source = readVersion();
	record("version has one source", Boolean(source) && source === pkg.version,
		source === pkg.version ? `both say ${pkg.version}` : `package.json says ${pkg.version}, src/__init__.py says ${source}`);

	record("licence field", Boolean(pkg.license),
		pkg.license ? pkg.license : "npm publishes without it, but it is the one field a lawyer reads");

	const licence = fs.existsSync(path.join(repoRoot, "LICENSE"));
	record("LICENSE file", licence, licence ? "the text travels with the tarball" : "no LICENSE in the repo root");

	const bundle = run(process.execPath, ["scripts/bundle.js", "--strict"]);
	record("bundle is in sync", bundle.ok, bundle.ok ? "the python tree matches the repo root" : bundle.err.split("\n")[0]);

	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "heyphony-preflight-"));
	let tarball = null;
	try {
		const pack = run("npm", ["pack", "--silent", "--pack-destination", tmp]);
		tarball = pack.ok ? newestTarball(tmp) : null;
		record("tarball builds", Boolean(tarball), tarball ? `${path.basename(tarball)}, ${Math.round(fs.statSync(tarball).size / 1024)} kB` : pack.err.split("\n")[0]);

		if (tarball) {
			const prefix = path.join(tmp, "prefix");
			const home = path.join(tmp, "home");
			fs.mkdirSync(home, { recursive: true });
			const install = run("npm", ["install", "-g", "--silent", "--prefix", prefix, tarball], { timeout: 240000 });
			record("the tarball installs", install.ok, install.ok ? `into ${prefix}` : install.err.split("\n").slice(-3).join(" "));

			const shim = path.join(prefix, "bin", "heyphony");
			if (install.ok && fs.existsSync(shim)) {
				const version = run(shim, ["--version"], { env: { ...process.env, HOME: home } });
				record("the installed command answers", version.ok && version.out.includes(pkg.version),
					version.ok ? version.out.split("\n")[0] : version.err.split("\n").slice(-2).join(" "));
				const status = run(shim, ["status"], { env: { ...process.env, HOME: home } });
				let parsed = false;
				try { JSON.parse(status.out); parsed = true; } catch (error) { parsed = false; }
				record("and it writes json", status.ok && parsed,
					parsed ? "status parsed on a machine with no config" : `status said: ${(status.out || status.err).slice(0, 120)}`);
			} else if (install.ok) {
				record("the installed command answers", false, "no bin/heyphony in the install prefix");
			}
		}
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true });
	}

	const who = run("npm", ["whoami"]);
	const loggedIn = who.ok && who.out && !who.out.includes("npm");
	record("npm is authenticated", loggedIn,
		loggedIn ? `as ${who.out}` : "run `npm login` (or set a granular access token), and have the 2FA code ready");

	const name = await registry(pkg.name);
	record("the name is yours to claim", name.free === true,
		name.free === true ? `${pkg.name} answers 404 on the registry, so it is unheld`
			: name.timeout ? "the registry did not answer, check the network"
			: name.free === false ? `${pkg.name} already exists${name.latest ? ` at ${name.latest}` : ""}${name.owner ? `, held by ${name.owner}` : ""}`
			: `could not check: ${name.error || "unknown"}`);

	const width = Math.max(...results.map((row) => row.name.length));
	for (const row of results) {
		const mark = row.ok ? "ok  " : row.blocking ? "stop" : "warn";
		console.log(`  ${mark}  ${row.name.padEnd(width)}  ${row.detail}`);
	}

	const blockers = results.filter((row) => !row.ok && row.blocking);
	console.log("");
	if (blockers.length) {
		console.log(`${blockers.length} thing${blockers.length === 1 ? "" : "s"} to fix before publishing:`);
		for (const row of blockers) console.log(`  - ${row.name}: ${row.detail}`);
		process.exit(1);
	}

	console.log("ready. the ceremony, in this order:");
	console.log("  1. bump __version__ in src/__init__.py, not package.json (the bundle syncs it)");
	console.log("  2. npm run preflight                     # this, again, on the bumped tree");
	console.log("  3. npm publish                           # 2FA code goes here");
	console.log("  4. npm view heyphony version dist-tags    # what the registry now holds");
	console.log("  5. npx heyphony@latest --version          # the only proof that matters");
	console.log("  6. git tag v<version> && git push origin v<version>");
	console.log("  7. flip the npm page and the root readme off \"not published\" in the same commit as the tag");
	console.log("");
	console.log(`  scoped fallback if the name is gone by then: npm publish --access public`);
	console.log(`  as @tinkrland/heyphony, after renaming the package and setting publishConfig.access`);
})().catch((error) => {
	console.error(`preflight crashed: ${error.message}`);
	process.exit(1);
});
