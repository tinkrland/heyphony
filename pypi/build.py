#!/usr/bin/env python3
"""build the pypi package from the repo, the way npm/scripts/bundle.js builds the npm one.

the repo keeps one copy of the code, at its own root, and imports it as `src`. a package called `src`
cannot go on pypi: it would install a top-level `src` into everyone's site-packages. so the build copies
src/ to pypi/heyphony/, rewrites `from src.x import y` to `from heyphony.x import y`, copies the prose
and data that ships beside the code, and leaves the repo itself untouched.

    python3 pypi/build.py            copy and rewrite into pypi/heyphony/
    python3 pypi/build.py --clean    remove every generated path again
    python3 pypi/build.py --wheel    build, then make sdist + wheel into pypi/dist/, then clean

the version is read from src/__init__.py, the single source. nothing here has a version of its own.
"""
import pathlib
import re
import shutil
import subprocess
import sys

PYPI = pathlib.Path(__file__).resolve().parent
REPO = PYPI.parent
OUT = PYPI / "heyphony"
GENERATED = [OUT, PYPI / "LICENSE", PYPI / "readme.md", PYPI / "dist", PYPI / "build", PYPI / "heyphony.egg-info"]

# prose that travels with the code: an agent reads these, so they are part of the product.
SHIPPED_DIRS = ["journal", "providers", "theidea"]
SHIPPED_FILES = ["directory.md", "logo.png"]

IMPORT = re.compile(r"^(\s*)(from|import)\s+src(\b)", re.M)


def version():
    text = (REPO / "src" / "__init__.py").read_text()
    return re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text).group(1)


def rewrite(text):
    return IMPORT.sub(lambda m: f"{m.group(1)}{m.group(2)} heyphony{m.group(3)}", text)


def copy_tree(src, dst):
    for item in sorted(src.rglob("*")):
        rel = item.relative_to(src)
        if "__pycache__" in rel.parts or item.suffix == ".pyc":
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.suffix == ".py":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rewrite(item.read_text()))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def clean():
    for path in GENERATED:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def build():
    clean()
    copy_tree(REPO / "src", OUT)
    # the data folders live inside the package so importlib.resources and __file__ both find them.
    for name in SHIPPED_DIRS:
        if (REPO / name).is_dir():
            copy_tree(REPO / name, OUT / "docs" / name)
    for name in SHIPPED_FILES:
        if (REPO / name).is_file():
            (OUT / "docs").mkdir(exist_ok=True)
            shutil.copy2(REPO / name, OUT / "docs" / name)
    shutil.copy2(REPO / "LICENSE", PYPI / "LICENSE")
    shutil.copy2(REPO / "readme.md", PYPI / "readme.md")
    print(f"built heyphony {version()} into {OUT.relative_to(REPO)}")


def main(argv):
    if "--clean" in argv:
        clean()
        print("cleaned")
        return 0
    build()
    if "--wheel" in argv:
        try:
            subprocess.run([sys.executable, "-m", "build", "--outdir", str(PYPI / "dist"), str(PYPI)], check=True)
        finally:
            for path in (OUT, PYPI / "LICENSE", PYPI / "readme.md", PYPI / "build", PYPI / "heyphony.egg-info"):
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
