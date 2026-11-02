# voicemail

a voicemail is two things that must not be separated: an audio file and a sidecar describing it. if the file arrives without the sidecar, the sender is unknown and the page says unknown rather than guessing from a filename.

```
~/.local/share/telephony/voicemail/
  vm-12125550143-0922.wav
  vm-12125550143-0922.json   {"from": "+12125550143", "seconds": 22, "transcript": "..."}
```

## transcript rules, which are the whole page

- if the vendor sends a transcript, keep it and say where it came from.
- if a carrier email happens to contain a body that is not the subject line, that body is the transcript.
- if neither, `transcript` is absent, and `heyphony open voicemail --show 1` says there is no transcript instead of producing one.
- no speech to text runs locally yet. when it does it will write its own field and name the engine, because a machine transcript that looks like a human one is worse than no transcript at all.

## playing one

`heyphony open voicemail --play 1` tries ffplay, then paplay, then aplay, and says plainly when none of them exist. on a host with no audio at all that is not a failure, it is a fact, and a headless host is exactly where this command is most likely to be run.
