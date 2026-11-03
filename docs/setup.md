# setup

two commands, two scopes. `bin/heyphony` gives an agent a number, and it lives on `main`. `bin/comms` tells it which other lanes exist and what each one costs to open, and that is this branch. everything under **telephony first** below is main's, kept here because a lane that borrows the number has to know how the number was set up.

```
git checkout omni
python3 tests/selftest.py       # the whole suite, stdlib only, no network
bin/heyphony --setup            # telephony: the number, the client, the proof
bin/comms --setup               # every lane, its gate, its honest state
```

## telephony first

a number is the lane that unlocks the others: signal needs one to register, and a meetings lane is more useful when people can also call.

`bin/heyphony --setup` prints the plan. `bin/heyphony setup select sip` walks it as menus (provider, then whether the did already exists, then the number), and the same three questions have flags so a process can answer them without a terminal: `--provider voipms|flowroute`, `--did +1...` or `--new`, `--json`. with no terminal and no flags it prints the next question instead of blocking. in short: pick from ten providers (`--provider voip.ms|flowroute|anveo|signalwire|questblue|bulkvs|jmp.chat|voyced|voxacall|bitcall`), seven of which can receive a text and three of which are voice only, then buy a did (from six cents at bulkvs to about five dollars at jmp.chat), and

```
export HEYPHONY_SIP_DID=+1...
bin/heyphony connect sip --voipms --did +1... --username ... --password ...
bin/heyphony serve --port 8099 --token ...     # provider sms webhook
bin/heyphony hooks <provider>              # what to paste, and the api call that arms it
bin/heyphony setup provision --provider anveo --areas --country-id US   # stock and prices, free
bin/heyphony setup provision --provider anveo --area-code 212            # the order call, prepared and unrun
bin/heyphony hooks bulkvs --apply          # arms it when the credentials are in the environment
```

ordering a number is the one step the cli will not take for you. area stock and prices are free to ask for, an order bills the account, and no payment rail is wired here on purpose: `--apply` runs the free steps and hands back the prepared `DID.ORDER` call, `--purchase` says parked rather than pretending, and `heyphony hooks anveo --apply --did <the number>` arms the texts on a number you bought yourself. area selection is first class because a number a human will be called back on is not "some number in your country": `--country-id`, `--state-id`, `--area-code` and `--area-name` all reach the provider's own lookup.

point the client at the generated rc on the host (baresip is the chosen client: json over tcp via `ctrl_tcp`), dial the provider echo test, text the number, and confirm both with `bin/heyphony calls` and `bin/heyphony inbox`.

once the number works, two things open up.

the setup plan now carries the two steps that used to be implied: **catching** (where a text lands, and the command that arms it) and **voicemail** (the carrier's fallback, or the honest sentence that this provider has none). `bin/heyphony app --port 8790` opens the launcher: three tabs for caught messages, voicemail and calls, one thread per person, and carrier emails parsed into messages with their audio attached. replies are drafted in the thread and never sent, because a half wired outbound path is worse than a draft that says what it needs.

read what arrived: `bin/heyphony open messages` (numbered rows, `--show 3`, `--mark-read 3`, `--unread`), `bin/heyphony open calls --missed`, `bin/heyphony open voicemail`. json only, no dashboard, and the read marks are ours because a webhook never tells you whether anyone looked.

and the rail signal needs: `bin/heyphony get signal` for the flow (the android spawnable signs up, the sms code arrives in the inbox above, the desktop then links to the phone as a secondary device), with the qr scan left to you.

## then whichever lanes you actually want

each folder's readme carries its own gate and its own proof. the short version:

```
export CARLYEMAIL_SIGNING_SECRET=...   # email,   /email
export PHOTON_SIGNING_SECRET=...       # imessage, /imessage
export WAHA_HMAC_KEY=...               # whatsapp, /whatsapp
export SLACK_SIGNING_SECRET=...        # slack,    /slack
export DISCORD_BOT_TOKEN=...           # watch
export ZOOM_SDK_KEY=... ZOOM_SDK_SECRET=...   # meetings
export LIVEKIT_URL=... LIVEKIT_API_KEY=...    # meetings audio
export TWITCH_CLIENT_ID=...            # streaming, api only; the go-live press stays a human's
```

`bin/comms serve --port 8098` catches the webhook lanes and stores every message as one envelope in the shared inbox. `bin/comms join --platform zoom --meeting N`, `bin/comms signal --path link-device`, `bin/comms go-live --platform twitch` return the plan for their lane instead of performing it, which is the point: an agent reads the plan, a person keeps the last press.

## the rules, which are not optional

- unset credentials close a lane. nothing is open by default.
- a config file is not proof. a lane becomes real when one real message carries through it.
- a group is never whitelisted, and a monitoring lane never answers.
- the sip secret lives on the host, never in a burnable guest.
- a did is voip: refused for otp, refused for bulk outbound.
- it renders, never publishes, except streaming where a human presses go live.
