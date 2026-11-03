# jmp.chat

a real number whose inbox is a chat client, which is either exactly what you want or the wrong shape entirely.

## how texts arrive

not by webhook. there is no url to give them: texts, picture messages and voicemail with transcription arrive **as jabber messages to your jid**. the delivery mechanism is a chat protocol, and that has one consequence worth reading twice: nothing in this repo can receive it, because there is no `POST` to catch and no `GET` to parse.

`sip_style` says `xmpp-first` and `text_style` says `xmpp`, and the hook kind is `xmpp`, which in this repo means the catcher does not handle it and says so rather than pretending an empty inbox is an empty number.

## what that is good for

- **a number that is genuinely yours**, at four dollars and change a month, in the united states and canada, with mms and transcribed voicemail included in the shape rather than as add-ons.
- **a client you already run.** if the agent already speaks xmpp, the inbox is where it already is, and there is nothing new to host.
- **a slower, more human interface.** the messages sit in a conversation, addressed to a jid, the way a person's phone treats them.

## what it is not

a webhook target. if the workflow needs "a text arrives while the machine is off and a process picks it up later", the xmpp client is the thing that must be running, and the reliability of that is your server's business, not the carrier's.

## outbound

**no http path.** sending is an xmpp message in the same conversation, not a rest call, so the send rail declines rather than wrapping a protocol it cannot test. the row in `heyphony send --paths` says `no http path`, and it is accurate.

## what is still unverified

no number has been bought here, and an xmpp lane has never been driven end to end by this repo. the shape of the arrival is from their own description of the service.

## setup sketch

1. buy the number, then point the jid at the client the agent will run
2. run that client somewhere that stays up, because it is the receiver
3. `heyphony connect sip --provider jmp.chat --did +1... --username ... --password ...` for the calls half, which is ordinary sip
4. text the number, then read it in the client, not in `heyphony inbox`
