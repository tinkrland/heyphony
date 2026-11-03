# signal

the lane that exists because heyphony exists. signing up for signal needs one thing:
a number that can receive an sms. that is a telephony problem, and heyphony is the
telephony folder, so the hard part is already in the branch.

## the one command

once heyphony has a number, opening this rail is one call:

```
heyphony get signal                 # the plan: install, join, verify, and what stays human
heyphony get signal --run           # actually pull and start the container
heyphony get signal --path register-number --run    # the other path, if you want its own identity
```

that is `heyphony get`, not `comms get`, on purpose. signal's only real prerequisite is a
number with an sms, and the package that holds the number is the package that can open the
rail. the recipe it executes is `heyphony/src/onramp/signal.json`, so what the command does is
readable and diffable instead of baked into a shell history. dry by default, because
installing is a real change, and the qr scan is never something the command does for you.

## the shape: a phone that idles, a desktop that works

the signup normally needs a handset in a hand. ours is a **durable but idle android
spawnable**, and the code that would land on that handset lands at **heyphony** instead,
because the number is a did whose texts the telephony package catches. so the sequence is:

1. the spawnable installs signal and enters the did as its number
2. signal texts a code. it arrives in heyphony's inbox, not on a screen
3. the agent reads it on the desktop (`heyphony open messages --unread`) and types it into the phone
4. the phone is now the identity of record, and it can go back to sleep: owning the account is not a job
5. the desktop links to it as a secondary device (`/v1/qrcodelink`, scanned from the phone), so the agent's own machine is a signal endpoint beside the phone

that last step is the point. one identity, two devices, the same relationship a person has
with their laptop. nothing here invents a second account to get a desktop session.

three paths, weakest last:

- **phone-signup** (default): the durable spawnable owns the account and heyphony reads the code.
- **link-desktop**: a phone already has signal, the desktop just attaches. no signup at all.
- **register-number**: signal-cli registers the did with no phone of record. signal is **far less
  strict about voip numbers than whatsapp or google**, so this is likelier to pass than the
  equivalent move anywhere else, but there is no device behind it and a captcha can appear.
  expect a challenge, do not promise a pass.

the transport is `signal-cli` (unofficial, and honest about it) or its rest wrapper.
nothing here reimplements libsignal and nothing here pretends signal has a bot api:
it does not, which is why the lane is a cli and a wrapper, not an oauth app.

gate: `SIGNAL_CLI_URL` (a running signal-cli-rest-api) or a linked device file.
