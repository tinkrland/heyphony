"""recognica: the contact book, split by who somebody is to the owner rather than by channel.

the agent's address book has a job a human's does not: it has to know which of these people is the
person it answers to. delegation makes that load bearing. a card in a flat list cannot say "this is
the owner, that is a client, that is another agent", and an agent that treats its owner like any
other inbound sender is not delegated to, it is adrift.

shelves, on disk, under COMMS_RECOGNICA_PATH:

    humans/owner/     the person the agent serves. exactly one, named rather than inferred.
    humans/people/    everybody else it talks to, on any lane.
    agents/           peers that are also software, kept apart so a machine is never mistaken
                      for a person who happens to write in a terse style.
"""
from comms.recognica import cards, roles

__all__ = ["cards", "roles"]
