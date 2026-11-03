# humans/owner

*the person this agent works for*

one card, and the only one on this shelf. the owner is not a special tag applied to a contact: it is a different shelf, because the difference is not cosmetic. this is the card an agent is entitled to act for.

how it gets here:

- `comms recognica --owner email:you@example.com` (repeatable, and phone or sms handles work too)
- `RECOGNICA_OWNER_EMAIL` and `RECOGNICA_OWNER_PHONE` in the environment, which a host deployment sets at provisioning time

how it does not get here: being the first card in the book, being the most frequent sender, or having a friendly name. an agent with a guessed owner is worse than an agent that says it does not know yet, so an empty shelf is a valid state and `comms recognica` reports it as one.
