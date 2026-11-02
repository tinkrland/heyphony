#!/usr/bin/env node
"use strict";

/*
 * bundle: put the python where the package can ship it.
 *
 * the repo keeps one copy of the code, at <repo>/heyphony. the npm package cannot reach outside
 * its own folder once it is packed, so it carries a copy made at pack time instead of a second
 * copy committed next to it. one source of truth, one direction of copy.
 *
 * run by `prepare` (after a git install, and by hand) and by `prepack` (before a publish or pack).
 * with --strict it refuses instead of warning, which is what the test suite and prepack want.
 */

const fs = require("fs");
const path = require("path");

const pkgDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(pkgDir, "..");
const source = path.join(repoRoot, "heyphony");
const target = path.join(pkgDir, "python", "heyphony");
const strict = process.argv.includes("--strict");

function fail(message, detail) {
  const line = detail ? `${message}\n  ${detail}` : message;
  if (strict) {
    console.error(`bundle: ${line}`);
    process.exit(1);
  }
  console.warn(`bundle: ${line}`);
}

function versionOf(file) {
  const text = fs.readFileSync(file, "utf8");
  const match = text.match(/__version__\s*=\s*["']([^"']+)["']/);
  return match ? match[1] : null;
}

function copyTree(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) continue;
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) copyTree(src, dst);
    else if (entry.isFile()) fs.copyFileSync(src, dst);
  }
}

function countFiles(dir) {
  let total = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory()) total += countFiles(path.join(dir, entry.name));
    else total += 1;
  }
  return total;
}

if (!fs.existsSync(source)) {
  fail(
    "the python source is missing, so this package cannot be built from here",
    `looked for ${source}. the npm folder is published from inside the heyphony repo, ` +
      `so run this from a clone of it, or install the cli with npx heyphony instead.`
  );
  process.exit(strict ? 1 : 0);
}

// the version lives in the python package, because the code is the thing that has a version.
const pyVersion = versionOf(path.join(source, "__init__.py"));
const pkgVersion = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8")).version;
if (!pyVersion) {
  fail("could not read __version__ from heyphony/__init__.py");
} else if (pyVersion !== pkgVersion) {
  fail(
    `version drift: package.json says ${pkgVersion}, heyphony/__init__.py says ${pyVersion}`,
    "bump both in the same commit, or let this script write the package version"
  );
  // a drift is not cosmetic: `npx heyphony@0.2.0` installing 0.1.0 code is a lie about what ran.
  const manifestPath = path.join(pkgDir, "package.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  manifest.version = pyVersion;
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`bundle: package.json version set to ${pyVersion} from the python package`);
}

fs.rmSync(path.join(pkgDir, "python"), { recursive: true, force: true });
copyTree(source, target);
const files = countFiles(target);
console.log(`bundle: ${files} files copied into python/heyphony, version ${pyVersion}`);
