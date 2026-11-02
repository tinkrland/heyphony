#!/bin/sh
# install heyphony from the url, with no npm and no clone.
#
#   curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh
#
# what it does, in four lines of intent: download the repo tarball for a ref, put it under
# HEYPHONY_HOME, link one shim onto your PATH, and tell you the two commands that come next.
# it installs nothing into a system directory, and re-running it is how you upgrade.
set -eu

REPO="tinkrland/heyphony"
REF="${HEYPHONY_REF:-main}"
HOME_DIR="${HEYPHONY_HOME:-$HOME/.local/share/heyphony}"
BIN_DIR="${HEYPHONY_BIN:-$HOME/.local/bin}"

say() { printf '%s\n' "$*"; }
die() { printf 'install: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 is required and was not found. install python 3.8 or newer, then run this again."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
  || die "python3 is $(python3 -V 2>&1), and heyphony needs 3.8 or newer."
command -v curl >/dev/null 2>&1 || die "curl is required and was not found."
command -v tar >/dev/null 2>&1 || die "tar is required and was not found."

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

say "install: fetching $REF from $REPO"
# a branch first, then a tag: HEYPHONY_REF takes either, and guessing from the name gets it wrong
# on any repo whose branches have dots in them.
if ! curl -fsSL "https://github.com/$REPO/archive/refs/heads/$REF.tar.gz" -o "$tmp/src.tar.gz" 2>/dev/null; then
  curl -fsSL "https://github.com/$REPO/archive/refs/tags/$REF.tar.gz" -o "$tmp/src.tar.gz" 2>/dev/null \
    || die "no branch or tag called $REF in $REPO"
fi

tar -xzf "$tmp/src.tar.gz" -C "$tmp" || die "the download did not look like a tarball"
inner=$(find "$tmp" -maxdepth 1 -type d -name 'heyphony-*' | head -1)
[ -n "$inner" ] || die "the tarball had no heyphony directory inside it"

mkdir -p "$HOME_DIR"
rm -rf "$HOME_DIR/app"
mkdir -p "$HOME_DIR/app"
cp -R "$inner"/. "$HOME_DIR/app"/ || die "could not write into $HOME_DIR/app"

chmod +x "$HOME_DIR/app/bin/heyphony"
mkdir -p "$BIN_DIR"
ln -sf "$HOME_DIR/app/bin/heyphony" "$BIN_DIR/heyphony"

version=$("$BIN_DIR/heyphony" --version 2>/dev/null || echo unknown)

say ""
say "install: heyphony $version is in $HOME_DIR/app"
say "install: linked $BIN_DIR/heyphony"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    say ""
    say "  $BIN_DIR is not on your PATH. add one line to your shell file:"
    say "    export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac

say ""
say "next, and this is the whole errand:"
say "  heyphony setup select sip     pick a provider, then a number, and it prints the connect line"
say "  heyphony status               what is registered, what arrived, what is unread"
say ""
say "an agent does not have to answer the menus: with no terminal it returns the next question"
say "as json, and every menu choice is also a flag. see npm/agents.md in the same repo."
