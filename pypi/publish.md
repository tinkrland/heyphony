# publishing to pypi: the same package, a second door

*`pip install heyphony` and `npm i -g heyphony` run the same code. this page is for whoever holds the pypi account, and stays out of the wheel.*

the repo keeps one copy of the code and imports it as `src`. a package called `src` cannot go on pypi, because it would install a top-level `src` into every user's site-packages and collide with anything else that did the same. so `pypi/build.py` makes the publishable shape at build time: it copies `src/` to `heyphony/`, rewrites `from src.x import y` to `from heyphony.x import y`, and ships the prose and data beside it. the repo is never edited by the build, and the generated copy deletes itself again, so a tree with no `.gitignore` cannot collect it.

the short version: **`python3 pypi/build.py --wheel`, install the wheel somewhere clean and run it, then `twine upload`.**

## what is true today

- the name `heyphony` answered **404** on pypi when this was written, which means unheld and claimable. it is not reserved. check again right before the first upload.
- the wheel and sdist build, pass `twine check`, and the installed wheel runs `--version`, `status`, `doctor` and `lookup` on python 3.8.20 and 3.11, with nothing from outside the standard library.
- nothing has been uploaded. `pip install heyphony` does not work until the first upload lands.

## the version, which lives in one place

`__version__` in `src/__init__.py` is the only version. `pyproject.toml` reads it (`dynamic = ["version"]`) and `build.py` reads it for its log line, so there is nothing to keep in step. bump the python file, never the toml. a pypi version is also permanent: a file name can be uploaded once, even if the release is deleted, so a wrong 0.3.0 is fixed with 0.3.1.

## before the first upload

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

pypi requires 2FA for uploads. the practical route is an **API token** from pypi.org, account settings, scope it to the project once the name exists (the first upload needs an account-wide token, so replace it with a project-scoped one straight after). it goes in `~/.pypirc` or `TWINE_PASSWORD`, mode `0600`, with `TWINE_USERNAME=__token__`. it is a password: never in the repo, never pasted into chat. if it ever was, rotate it.

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

the readme's install section says pypi is built but not published until it is. flip those sentences in the same commit as the upload, and `git tag` the version. the test suite pins the sentences, so it fails until they are flipped, which is the point.

## the floor is python 3.8

`requires-python` is `>=3.8`, matching the npm shim. this was checked by running the whole suite and the installed wheel under a real 3.8.20, which found one thing a grammar check had missed (a dict `|` operator, 3.9 and later, in anveo provisioning). a test now reads every source file for that class of thing, so the floor stays true.
