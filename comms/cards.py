"""moved: the card lives under recognica now, because a card is an address book entry.

this shim exists so older callers keep working, and so the move is visible in one line rather than
in a rename nobody wrote down. new code should import from comms.recognica.
"""
from comms.recognica.cards import *  # noqa: F401,F403
