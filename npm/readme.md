# npm: the truck, not the lane

*heyphony is python. this folder exists so a machine with node on it can still get a number in one command.*

`npm i -g heyphony` is the shortest sentence between "i have a computer" and "my agent can be texted", and it is worth building even though not one line of the telephone is javascript. the split is simple: the python tree at the repo root, one level up, is the thing that does the work, and this folder packs that tree into a tarball with a fourteen line shim in front of it. the shim finds a python, points it at the code shipped beside it, and gets out of the way. it does not parse heyphony's output, it does not answer for it, and it holds no state.

so this is not a node library, and calling it one would be a small lie that costs somebody an afternoon. there is no `require("heyphony")`. there is one executable, and it is the same executable you get from a clone.

## install it

| how | command | needs |
| --- | --- | --- |
| one url, no node, no clone | `curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh \| sh` | `curl`, `tar`, `python3` |
| from a clone | `git clone https://github.com/tinkrland/heyphony && cd heyphony && ./bin/heyphony status` | `git`, `python3` |
| npm, from the tarball | `cd npm && npm pack && npm i -g ./heyphony-0.3.0.tgz` | `node`, `python3` |
| npm, once it is published | `npm i -g heyphony` | `node`, `python3` |
| npx, once it is published | `npx heyphony status` | `node`, `python3` |

the url install is the one to reach for when the answer has to be a single line, because it is the only path that needs neither node nor git. it downloads the repo tarball into `~/.local/share/heyphony/app`, links one shim into `~/.local/bin`, checks the python version before it starts, and installs nothing into a system directory. re-running it is how you upgrade. `HEYPHONY_HOME`, `HEYPHONY_BIN` and `HEYPHONY_REF` move those three assumptions if they do not fit.

### what is true, and how it was proved

`heyphony@0.3.0` is on the npm registry, published 2026-11-03. so `npm i -g heyphony` and `npx heyphony` are live routes rather than the two rows that 404. the proof was not the publish command returning zero: it was a clean prefix installing the tarball from the registry and the installed command answering 0.2.0, and `npx heyphony@latest --version` doing the same in an empty home.

a first publish is not instant on npm. a brand new package name goes through staged publishing, which claims the name with a `0.0.0-stage` placeholder while the real tarball is scanned, and the version appears a couple of minutes later. `npm publish` run again during that window answers 409, which is the registry saying the version is already staged rather than lost. the whole sequence, and what the next release has to do differently, is in [publish.md](publish.md).

what is still not true: this package ships the code and not the microphone, and nothing here has placed a real call yet. that has not changed.

the other thing worth knowing: a github install such as `npm i -g github:tinkrland/heyphony` does not work, and it is not an oversight. that form wants `package.json` at the repo root, and this repo keeps the code at the root and the packaging in `npm/`, because the code is the point and the packaging is scaffolding around it. use the tarball or the url.

## what the tarball carries

`npm pack` runs `scripts/bundle.js` first, which copies the repo root into `python/` and skips `__pycache__`. **the repo keeps one copy of the code and the package carries a copy made at pack time**, not a second copy committed next to it, because two copies of a lane is how they drift apart while both look maintained.

the version has one source too. `__version__` in `../src/__init__.py` is the real one, and the bundle copies it into `package.json` rather than letting the two disagree, on the theory that `npx heyphony@0.3.0` running 0.2.1 code is a lie about what executed. the strict mode the test suite and `prepack` use fails instead of warning.

one known gap: this package ships the code and not the microphone. `heyphony serve` listens on a port and `heyphony app` renders a page, and neither survives the shell that started it, because no unit file ships for systemd or launchd yet. `../src/runner/readme.md` says the same thing in the same words. if an agent needs the catcher up permanently, that is a decision about where the number lives, which is what the `setup` branch of this repo is for.

## for the thing doing the installing

an agent that installs this does not stop at `--version`. it wants to know what the next question is, and whether that question is for it or for its human. the short version is in [agents.md](agents.md): four commands, and the two places where a person has to be involved.
