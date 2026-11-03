"""where the number lives, seen from this branch's side of the one-way dependency.

omni imports heyphony and never the reverse, and that shows up here as one call: the inbox a message
is stored in belongs to the number, not to this branch. the import is lazy because a lane's gates,
signatures and payload shapes are this branch's own business, and only storing a message needs the
other half to be there at all.

two ways it resolves, in the order a reader would try them: `heyphony.src` when the package tree is on
the path, `src` when this branch is sitting inside a heyphony checkout. neither is a fallback that
invents a third behaviour: if the number is not reachable, the error says so when a message arrives
rather than at import time, when nothing has been asked for yet.
"""


def inbox():
    """the number's inbox module, or an error naming the two ways to make it reachable."""
    try:
        from heyphony.src import manage as module      # the package tree, installed or on pythonpath
    except ImportError:
        try:
            from src import manage as module           # this branch inside a heyphony checkout
        except ImportError as exc:
            raise ImportError(
                "the number is not on the path: put a heyphony checkout (or its python/ tree) on "
                "PYTHONPATH, or run this from inside one, and the inbox resolves"
            ) from exc
    return module


__all__ = ["inbox"]
