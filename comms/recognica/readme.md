# recognica

*the contact book, sorted by who somebody is rather than by which app they used*

an agent's address book has one job a human's does not: it has to know **which of these people it answers to**. that sounds like a detail until the agent is delegated real work, at which point the difference between "my owner asked me to send the invoice" and "somebody who has texted twice asked me to send the invoice" is the entire safety story.

recognica is that book. it keeps one card per person across every lane, and it puts each card on a shelf that says what the person is to the owner: the person served, a person talked to, or another piece of software.

```
recognica/
  humans/
    owner/     the person the agent serves. exactly one, named, never inferred
    people/    everybody else it talks to, on any lane
  agents/      peers that are also software, kept apart on purpose
```

## the shelves do the work

a flat list of cards cannot tell an owner from a stranger, and a `role: owner` tag on a card is a thing somebody forgets to set. so the shelf is the storage: a card under `humans/owner/` is served, a card under `agents/` is a peer, and everything else is a contact. `comms recognica` prints the tree, and the tree is the answer to "who is this agent working for".

three rules follow from that, and they are the same three the card always had, plus one:

**a card is a contact until somebody says otherwise.** a new card is never the owner. the owner is created by naming one, or by `RECOGNICA_OWNER_EMAIL` / `RECOGNICA_OWNER_PHONE` in the environment, which is what a host deployment actually has.

**a handle belongs to one card.** a second card claiming it is a merge, and a merge needs the dropped card's name typed, because merging the wrong two people is impersonation with extra steps.

**an unknown sender is not a card yet.** being messaged does not make somebody known. the message is stored, the stranger stays a stranger, and the absence of a card is said out loud rather than smoothed into a guess.

**an agent is not a person who writes terse messages.** other agents get their own shelf so a machine peer never inherits the permissions of a human contact, and so the book can be handed over without a stranger's bot sitting in the address book looking like a client.

## the card

a card is small on purpose: an id, a name, handles per channel, a kind (`human` or `agent`), a role (`owner` or `contact`), an optional note, and when it was made. because every lane produces the same envelope, a message from any handle resolves to the same card, and `digest()` is the thing the human used to do by hand: the last few things said across every channel, in one order.

handles are canonicalised per channel, because the same person writes their number four ways and one of them has to win. platform ids are left exact, since a guessed normalisation loses people.

## what it is not

it is not a crm, an identity provider, or a verification scheme. it does not prove that the person on the other end is who the card says, because nothing in messaging does. it records what the agent has been told and refuses to fill the gaps with assumptions, which is the only claim worth making about a contact book a model reads.
