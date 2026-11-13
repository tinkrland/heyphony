# publishing to pypi: the same package, a second door

*`pip install heyphony` and `npm i -g heyphony` run the same code. this page is for whoever holds the pypi account, and stays out of the wheel.*

the repo keeps one copy of the code and imports it as `src`. a package called `src` cannot go on pypi, because it would install a top-level `src` into every user's site-packages and collide with anything else that did the same. so `pypi/build.py` makes the publishable shape at build time: it copies `src/` to `heyphony/`, rewrites `from src.x import y` to `from heyphony.x import y`, and ships the prose and data beside it. the repo is never edited by the build, and the generated copy deletes itself again, so a tree with no `.gitignore` cannot collect it.

the short version: **`python3 pypi/build.py --wheel`, install the wheel somewhere clean and run it, then `twine upload`.**

## what is true today

- `heyphony 0.3.0` is on pypi, uploaded 2026-11-13, so `pip install heyphony` works. the files are the wheel and the sdist built here from the tree at `5500104`.
- the wheel on the index was installed into a clean 3.8.20 and a clean 3.11 and answered `--version`, `doctor` and `live` out of each, with nothing from outside the standard library.
- its code is that commit plus the import rewrite and nothing else. the wheel's `heyphony/` was diffed file by file against `src/` at `5500104`, and the only differences were the rewritten imports.
- the name is held by this project now, so a later upload wants a project-scoped token and a version nobody has taken.
- the tag `v0.3.0` marks the **npm** release and points at an older commit, not at this upload. do not move it: the commit named above is the wheel's record.

## the version, which lives in one place

`__version__` in `src/__init__.py` is the only version. `pyproject.toml` reads it (`dynamic = ["version"]`) and `build.py` reads it for its log line, so there is nothing to keep in step. bump the python file, never the toml. a pypi version is also permanent: a file name can be uploaded once, even if the release is deleted, so a wrong 0.3.0 is fixed with 0.3.1.

## before an upload

```
python3 -m pip install build twine
python3 pypi/build.py --wheel          # makes pypi/dist/*.whl and *.tar.gz, then removes the copy
python3 -m twine check pypi/dist/*
```

then the proof that matters, which is installing the wheel and not the tree:

```
python3 -m venv /tmp/pv && /tmp/pv/bin/pip install pypi/dist/*.whl
HOME=$(mktemp -d) /tmp/pv/bin/heyphony --version
HOME=$(mktemp -d) /tmp/pv/bin/heyphony status
```

`--version` must print the number in `src/__init__.py`, and `status` must print json. a wheel that builds is not a wheel that runs.

## the account, and a token

pypi requires 2FA for uploads. the practical route is an **API token** from pypi.org, account settings, scope it to the project, because the name exists now. only an account-wide token can create a name, which is why the first upload could not be project-scoped; every one after it can be. it goes in `~/.pypirc` or `TWINE_PASSWORD`, mode `0600`, with `TWINE_USERNAME=__token__`. it is a password: never in the repo, never pasted into chat. if it ever was, rotate it.

to rehearse without spending a version, upload to **TestPyPI** first (`twine upload --repository testpypi pypi/dist/*`). its names are separate, so a success there says the metadata and the wheel are acceptable, and nothing about the real name.

## the upload

```
python3 -m twine upload pypi/dist/*
```

then poll rather than re-upload: `pip index versions heyphony`, or `curl -s https://pypi.org/pypi/heyphony/json`. after it shows, prove it from the registry in a clean environment:

```
python3 -m venv /tmp/pr && /tmp/pr/bin/pip install heyphony
/tmp/pr/bin/heyphony --version
```

## the same commit as the upload

the readme's install section and this page say the same thing about what pypi has, and the suite fails when they disagree. 0.3.0 is when the sentences flipped from "not uploaded yet" to published, so that is also the moment the test had to flip with them rather than being deleted.

two things worth writing down, because both cost a round trip:

- **testpypi rejects a pypi token.** they are separate accounts with separate databases, so `twine upload --repository testpypi` answers 403 Forbidden however good the real token is. a test run there needs its own account and its own token, and without one the rehearsal is the local one: `twine check`, then install the wheel into a clean venv with `--no-index --find-links dist`, then run `--version`, `doctor` and `live` out of that environment. that is what happened for 0.3.0.
- **the version is spent on upload, not on approval.** pypi takes the files the moment twine finishes, so there is no staged state to wait out and no second chance at 0.3.0. the local rehearsal above is the only safety net there is.

## the floor is python 3.8

`requires-python` is `>=3.8`, matching the npm shim. this was checked by running the whole suite and the installed wheel under a real 3.8.20, which found one thing a grammar check had missed (a dict `|` operator, 3.9 and later, in anveo provisioning). a test now reads every source file for that class of thing, so the floor stays true.
