# publishing it: the ceremony, and the two things that are permanent

*`npm publish` is one command and four irreversible facts, so the runbook is written before it is needed*

this page is for whoever is holding the npm account, not for the agent installing the package. it stays out of the tarball (the `files` list in `package.json` does not include it), because a user does not need the maintainer's checklist and a tarball should not carry one.

the short version: **`npm run preflight`, then `npm publish`.** everything else on this page is why those two, and what to do when they say no.

## what has to be true before the first publish

### an account, and 2FA on it

the registry has required two-factor auth for publishers for years, and it will ask for the code at publish time rather than at login. `npm login --auth-type=web` is the shortest path: it opens a browser, comes back with a token, and leaves the 2FA dance where it belongs.

if the publish has to happen from a machine with no browser, or from CI, the answer is a **granular access token** with read and write on the package and `bypass 2FA` ticked, stored as `NODE_AUTH_TOKEN`. that token is a password: `0600`, never in the repo, and `npm/preflight` checks `npm whoami` rather than assuming.

### the name, claimed before somebody else does

`heyphony` answers **404** on the registry today, which means unheld and claimable. it is not reserved: a 404 is an invitation, not a hold. if it goes, the fallback is a scoped name, which publishes private by default and therefore needs `--access public`:

```
npm publish --access public     # as @tinkrland/heyphony, after renaming the package
```

a scoped name is a different package rather than a rename, so `npx heyphony` and `npx @tinkrland/heyphony` are different instructions forever. claim the bare name first if it is still there.

### the version, which lives in one place

`__version__` in `src/__init__.py` is the source of truth and `scripts/bundle.js` copies it into `package.json` at pack time. bump the python file, never the json, or the two disagree and the strict bundle refuses. `preflight` compares them and fails on a mismatch, because `npx heyphony@0.3.0` running 0.2.0 code is a lie about what executed.

## the publish itself

```
npm run preflight        # every check, cheapest first, and the last two actually install and run it
npm publish              # 2FA code goes here
```

`preflight` packs a real tarball into a temp directory, installs it globally into a temp prefix with a temp `HOME`, and then runs `heyphony --version` and `heyphony status` out of that prefix. that is the difference between "the bundle ran" and "the thing a stranger installs works", and it is the check worth keeping.

`prepublishOnly` runs the test suite, so a broken bundle cannot reach the registry even if the preflight is skipped. belt and braces, deliberately.

## the four permanent things

### a version number cannot be reused

not after an unpublish, not after a mistake, not ever. if 0.2.0 is published with a typo, the fix is 0.2.1. this is why the tag comes after the publish rather than before: the registry is the record, and the tag should follow what actually happened.

### an unpublish is a 72 hour window, and then it is not

inside 72 hours a version can be unpublished; after that, `npm deprecate` is the only lever, and it leaves the code downloadable with a warning. deprecate rather than delete, always: somebody's `npm i` may already be pinned.

### the tarball is public forever

every published version stays downloadable, which means anything packed into it is disclosed: no credentials, no internal hostnames, no scratch files. this package ships python and prose and nothing else, and `files` is a list rather than a wildcard so a stray file in `npm/` cannot sneak in.

### the readme is the package page

npm renders the package readme from the published tarball, so `npm/readme.md` is a *public* page the moment the publish lands, and right now it says, correctly, that nothing is on the registry. the flip is part of the publish, not an afterthought:

- `npm/readme.md`: the "nothing is published to the npm registry" paragraph becomes the published version and the current version number, and the two rows that said "once it is published" lose that qualifier
- `readme.md` (root): "nothing here is on the npm registry yet" becomes the claim that it is
- `tests/selftest.py` pins both sentences on purpose, so the suite fails until they are flipped together. that test is not an obstacle, it is the reminder.

## after it lands

```
npm view heyphony version dist-tags     # the registry's own answer
npx heyphony@latest --version           # the proof, on a machine that is not this one
npm owner add <collaborator>            # if anyone else should be able to publish or deprecate
```

`npx heyphony` is the row that changes a person's day: before the publish it 404s, and after it, an agent with node and python3 has the cli in one command with nothing installed permanently. that is the whole reason the npm folder exists beside a working `bin/heyphony`.

## what this does not solve

- **no CI publish.** automating it needs the granular token as a repository secret plus a workflow, and a token with publish rights sitting in a repo is a decision rather than a step. do it after the first manual publish proves the artifact.
- **no provenance attestation.** `npm publish --provenance` ties a tarball to a public GitHub Actions run, which is the right thing eventually and needs the CI above.
- **no automatic version bumping.** one file, bumped by hand, checked by a machine. for a package that ships 250 kB of python, that is the correct amount of ceremony.
