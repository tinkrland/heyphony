# outgoing: what leaves, gated, one message at a time

this lane used to be drafts only, and the reason was the right one: sending is the half of telephony where a mistake is not a bug, it is a message a real person reads. it is built now, deliberately, and it is the narrowest version that is still useful.

the rail lives in `send.py`, and it answers to four rules that are checks rather than documentation:

**the gate, and the ask.** `HEYPHONY_SEND=allowed` in the environment opens the rail; `--send` on the call asks it to use the rail. either alone produces a draft, and the draft prints the exact request so it can be read before it becomes real. a closed gate is not a warning to click past.

**one recipient.** a comma, a list, or a loop is refused by `one_recipient`. a campaign is a different product with consent, attested origination and a registered business behind it, and no flag here turns this into one.

**a documented path or nothing.** voip.ms, flowroute and signalwire each have a send path from their own documentation, linked in the table. anveo, jmp.chat, voyced, voxacall and bitcall can receive and cannot send through this lane, and the refusal names the three that can rather than failing deeper with a 404.

**no half configuration.** a missing credential is a refusal that names the variable. nothing authenticates as nobody.

## what it costs, and who carries it

**sms on this number, paid per message, by you.** the vendor charges for outgoing, which is why the package is inbound first: receiving is cheap or free, sending costs money per message, and a tool that sends on its own is a tool that spends on its own. there is no balance in here and no wallet: the provider holds the account.

**the terms are the operator's.** consent, quiet hours, opt-out language, a2p registration where the provider requires it, and what the recipient actually agreed to. a tool that respects a gate cannot also audit a business, and pretending otherwise would be the dishonest version of a safety feature.

**mms is refused, not missing.** no vendor in the table offers outbound mms in a way worth pretending about, so a link is the honest substitute and the one that survives a carrier that mangles a picture. inbound audio is already handled: an attachment with an audio content type is written next to the voicemail sidecar.

## what a message becomes

a sent message is stored in the same inbox as everything that arrived, with `direction: "out"`, so the thread holds both halves of the conversation and an agent reading `heyphony open messages` sees its own reply where a person would see it in the history. the provider's status code and the first bytes of its answer are kept in `raw`, because "it said success" and "the message arrived" are still two different claims.

`heyphony send --to +1... --text "..."` drafts. add `--send` with the gate open and it sends. `--no-store` sends without recording it, which is for a test and nothing else.

## the first real send

no message has been sent through this rail yet, so every provider row says `verified: false` and the status codes are expectations rather than observations. the first one should go to your own phone, from the did the provider actually holds, and the thing to check is that it arrives and that `heyphony open messages` shows it as outbound in the same thread as the reply.
