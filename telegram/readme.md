# telegram

the easiest lane in the branch, and it is worth saying why rather than being suspicious of it.

the bot is the half of telegram that needs no number, and it is also the half this lane reads. if the number half is ever wanted (an account rather than a bot), the recipe is `heyphony get telegram --path user-account` in the heyphony package, which holds the did and catches the signup code.

## one endpoint, one header

a telegram bot is an https webhook with a secret token in a header that telegram echoes back on every
update. there is no signature to rebuild over a body, no freshness dance, no unofficial bridge
holding somebody's phone session open: `setWebhook` with a `secret_token`, then compare
`x-telegram-bot-api-secret-token` in constant time. that is the whole gate, and it is the strongest
kind of gate there is, which is one that is boring enough to be implemented correctly.

the lane is still gated twice, because a valid signature only proves telegram sent it:

- `TELEGRAM_WEBHOOK_SECRET` unset closes the lane. an unset secret is a closed door, not an open one.
- `TELEGRAM_ALLOWED_CHATS` is a comma separated list of chat ids. unset means nobody, because the
  default for a stranger is that they are a stranger.

## a room is not a person

telegram makes groups trivially easy to join, which is exactly why they are refused: a message in a
group is a room talking, not somebody asking. same rule as whatsapp, same reason. channels and
supergroups get a 403 with the refusal named rather than a silent drop, so the log says why nothing
happened.

## what arrives

one update becomes one envelope like every other carrier: `id` (the update id, so a redelivery
dedupes), `channel: telegram`, `direction: in`, `sender` (the username, or the numeric id when there
is no username), `body` (text or caption), `thread` (the chat id, which is what a reply addresses),
and `raw`. media-only messages normalise with an empty body and keep their raw payload, because
dropping what we cannot read yet is worse than storing it.

## what does not

sendmessage is a plain http call with a bot token, so replying is possible and deliberately narrow:
one chat, one message, human pace. no broadcast, no list of ids, no "notify everyone who ever
messaged us". a bot api key is a durable credential, so it belongs to whoever runs the catcher, never
to a guest we intend to burn.

```
TELEGRAM_BOT_TOKEN=...  TELEGRAM_WEBHOOK_SECRET=...  TELEGRAM_ALLOWED_CHATS=12345678,87654321
bin/comms serve --port 8098    # /telegram joins /email /imessage /whatsapp /slack
```
