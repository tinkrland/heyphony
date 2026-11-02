# messages

a text arrives one of two ways, and which one you get is decided by the vendor, not by this package.

**posted to a url.** the catcher serves `/sms/<vendor>`, the vendor posts json or a form, and `routes.py` normalizes it. this needs the host awake.

**emailed to you.** voip.ms emails the text, jmp.chat delivers it to jabber. `mailparse.py` turns the email into the same row, which is why sms survives a machine that is asleep. the cost is latency and a mailbox that fills up; the benefit is that the number is never deaf.

what a message row looks like after both roads:

```json
{"id": "sms:abc123", "channel": "sms", "direction": "inbound", "sender": "+12125550143",
 "body": "are you free at 3?", "at": 1793523600, "thread": "+12125550143", "raw": {"provider": "voip.ms"}}
```

the thread key is the other party, so the launcher can show one conversation per person instead of one inbox per vendor. that is the whole trick behind the page: a person does not think in channels and a phone is not a channel, it is a person.
