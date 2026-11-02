# inbox: what arrived

one page per kind of thing, because they arrive by different roads.

- [messages](messages.md): texts, which never travel over sip and always come from a vendor posting or emailing them.
- [voicemail](voicemail.md): a recording plus a sidecar, and the transcript rules.
- [missed](missed.md): calls that rang and were not answered, read from the client's own history.

## one shape, one file

everything lands in a jsonl file, one row per message, with the same keys whichever channel it came from: id, channel, direction, sender, recipient, subject, body, at, thread, reply_to, raw. the raw payload is kept, because the day a vendor changes its field names is the day the raw copy is the only thing that can explain what happened.

deduplication is by the provider's own id, so a webhook that retries four times is one message. when a vendor sends no id, one is derived from the sender, the body and the timestamp, which is stable enough for a retry and honest enough to be wrong exactly once.

read state lives beside the file rather than in it, because a delivery is not a read and a provider never tells you one happened.
