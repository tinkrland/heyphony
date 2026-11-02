#!/usr/bin/env node
"use strict";

/*
 * bundle: put the code where the package can ship it.
 *
 * the repo keeps one copy of the code, at its own root: src/, journal/, providers/, theidea/, the
 * readme, the directory map and the licence. the npm package cannot reach outside its own folder once
 * it is packed, so it carries a copy made at pack time instead of a second copy committed next to it.
 * one source of truth, one direction of copy, and the copy is deleted again by `postpack`.
 *
 * run by `prepack` (before a publish or pack) and by hand with `npm run bundle`. with --clean it
 * removes the copy, which is what `postpack` does, so a tree with no .gitignore still cannot collect a
 * generated directory that nobody meant to commit. with --strict it refuses instead of warning, which
 * is what the test suite and prepack want.
 */

const fs = require("fs");
const path = require("path");

const pkgDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(pkgDir, "..");
const target = path.join(pkgDir, "python");
const strict = process.argv.includes("--strict");
const clean = process.argv.includes("--clean");

// the packaging folders are not the product. everything else at the root is, and it ships as it is:
// the prose is part of what an agent reads, and the licence has to travel with the code.
const SKIP = new Set([".git", ".github", "npm", "tests", "bin", "node_modules", "__pycache__"]);

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

function copyTree(from, to, skip) {
  fs.mkdirSync(to, { recursive: true });
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    if (skip && skip.has(entry.name)) continue;
    if (entry.name === "__pycache__" || entry.name.endsWith(".pyc")) continue;
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) copyTree(src, dst, null);
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

if (clean) {
  fs.rmSync(target, { recursive: true, force: true });
  fs.rmSync(path.join(pkgDir, "LICENSE"), { force: true });
  console.log("bundle: the copy is gone, so the tree holds nothing generated");
  process.exit(0);
}

if (!fs.existsSync(path.join(repoRoot, "src", "runner", "cli.py"))) {
  fail(
    "the code is missing, so this package cannot be built from here",
    `looked for ${path.join(repoRoot, "src", "runner", "cli.py")}. the npm folder is published from ` +
      `inside the heyphony repo, so run this from a clone of it, or install the cli with npx heyphony.`
  );
  process.exit(strict ? 1 : 0);
}

// the version lives in the code, because the code is the thing that has a version.
const pyVersion = versionOf(path.join(repoRoot, "src", "__init__.py"));
const pkgVersion = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8")).version;
if (!pyVersion) {
  fail(`could not read __version__ from ${path.join(repoRoot, "src", "__init__.py")}`);
} else if (pyVersion !== pkgVersion) {
  fail(
    `version drift: package.json says ${pkgVersion}, src/__init__.py says ${pyVersion}`,
    "bump both in the same commit, or let this script write the package version"
  );
  // a drift is not cosmetic: `npx heyphony@0.2.0` installing 0.1.0 code is a lie about what ran.
  const manifestPath = path.join(pkgDir, "package.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  manifest.version = pyVersion;
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`bundle: package.json version set to ${pyVersion} from the code`);
}

fs.rmSync(target, { recursive: true, force: true });
copyTree(repoRoot, target, SKIP);
const files = countFiles(target);
console.log(`bundle: ${files} files copied into python/, version ${pyVersion}`);

// the licence travels with the tarball, and npm only looks inside the package folder for it, at the
// top. the copy inside python/ is for whoever reads the code; this one is for the registry.
const licenceSource = ["LICENSE", "LICENSE.md", "LICENCE"].map((name) => path.join(repoRoot, name))
  .find((candidate) => fs.existsSync(candidate));
if (licenceSource) {
  fs.copyFileSync(licenceSource, path.join(pkgDir, "LICENSE"));
  console.log(`bundle: ${path.basename(licenceSource)} copied beside the package`);
} else {
  fail(
    "no LICENSE at the repo root, so the tarball ships without one",
    "npm publishes happily without a licence field and it is the one field a lawyer reads first"
  );
}
