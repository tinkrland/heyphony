# for the agent doing the installing

*you have a shell, no patience for a wizard, and no hands to click a portal. this page is the errand, in the order it actually runs.*

heyphony is built for you first, which shows up in one design decision repeated everywhere: **every menu is also a flag, and a run with no terminal returns the next question instead of waiting for an answer.** nothing blocks on stdin, nothing prints a progress bar you have to strip, and every command writes json. the menu in `heyphony setup select sip` exists because a person sometimes runs it too, not because you have to watch it.

## the four commands

```
heyphony setup                     the whole plan as json: the provider you picked, the connect line,
                                   where texts land, which voicemail to expect, and the proof steps
heyphony setup select sip          the same errand, one question at a time
heyphony hooks <provider> --apply  arms the provider's text url so an inbound text has a home
heyphony doctor                    what is actually true right now, including what is only designed
```

`setup select sip` on a machine with no terminal answers like this, and the shape is the contract:

```json
{ "ok": false, "needs": "provider", "flag": "--provider", "options": [ ... ] }
```

that is not an error to retry, it is the next question. answer it with the flag (`--provider anveo`), and the next call asks the next question the same way. three answers finish the errand: provider, then whether the did already exists, then the number. **do not loop on a `needs` answer**, because the absence of a terminal will not change between two identical calls; if the question is one only your human can answer, it is time to say so.

## the two places a person has to be involved

the claim worth making carefully, because it is the one that survives contact with reality: heyphony removes the clicking, the signing and the container keeping, and it cannot remove two things that are not technical.

**paying for the number.** a purchase is a purchase, so the payment step stays a human's for every provider, including the one whose whole ordering chain is scriptable. `heyphony provision` prepares the order, prices it, names the rate plan, and stops at the money rather than pretending a card exists.

**a credential that only exists in somebody's dashboard.** the sip username and password come from a provider portal, so the connect line has `<sip username>` and `<sip password>` sitting in it as placeholders. that is deliberate: a plan with a plausible looking fake in it is worse than a plan with a hole you can see. paste them once, and `heyphony connect` writes `~/.config/linphone/linphonerc` at mode 0600 because it is a password in a text file.

## what you leave behind

| path | what it is |
| --- | --- |
| `~/.config/linphone/linphonerc` | the registration, 0600, one did one registration |
| `~/.local/share/telephony/inbox.jsonl` | caught messages, one envelope per line, deduped by provider id |
| `~/.local/share/telephony/read-marks.json` | what you have read, because no provider tells us |
| `~/.local/share/telephony/voicemail/` | audio plus a sidecar per voicemail, no sidecar means no transcript |

after the number answers, you live in one command: `heyphony open messages --unread`. rows are numbered, carry a stable handle, and preview sixty-four characters, which is the difference between reading an inbox and loading a mailbox. `--show N` expands exactly one body.

## what is refused, so you do not waste a turn

a did is voip, and voip numbers are refused by exactly the flows most likely to be asked for. so there is no otp story here, no bulk outbound path, and no "warm the container so a text can arrive" trick, because texts never travel over sip and arrive whether the machine is awake or not. the outgoing lane keeps drafts and does not send. a reply is allowed, one message at a time: `heyphony send --to +1... --text "..." --send` needs `HEYPHONY_SEND=allowed` in the environment and one recipient, and it records what it sent in the same thread. a list, a loop or a schedule is refused by the rail itself. if a task needs to blast a hundred messages or verify an account by sms, stop before the attempt and say why: `src/manage/outgoing/readme.md` is the page that has the argument.
