# the proof step

setup ends with a claim, and this folder is about not believing the claim until something arrives. there is no separate `setup test` subcommand, and inventing one that prints green ticks would be worse than having none: the proof is `heyphony doctor` for configuration, then one real message from a phone that is not yours.

## what doctor answers

```
heyphony doctor
```

- `host_client`: which client was chosen for scripted call control, and why.
- `rc_present`: whether a registration has actually been written on this host.
- `inbox`: how many messages have ever arrived.
- one honest line: nothing here has placed a call yet, and a lane with credentials and no live call is designed, not verified.

## what counts as proof, per lane

| lane | proof | not proof |
| --- | --- | --- |
| texts | a real sms from a stranger's phone appears in `heyphony open messages` | the hook url returns 200 when you curl it |
| voicemail | a real unanswered call leaves an audio file and a sidecar with its sender | the vendor's portal says voicemail is on |
| calls | one real call rings the host client, and `heyphony calls` shows it afterwards | a registration showing as registered |
| email forwarding | a forwarded carrier email imports with its audio attached | the mailbox receiving a test message you sent yourself |

three of those four rows can only be satisfied by a human dialing a number, which is why this page ends in an instruction rather than a command. the one thing the suite can do is refuse to call a lane verified before that happens, and it does: every vendor stays `verified: false` in `src/providers.py` until a real delivery lands.
