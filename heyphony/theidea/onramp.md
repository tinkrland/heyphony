# onramp

*the ramp for signal, and the boundary that keeps it a ramp*

a phone number is not useful only for being a phone number. it is a **prerequisite**. a surprising number of things that an agent would like to use will not talk to a program at all, and will happily accept a phone instead. a number is the key those doors were fitted with, thirty years before anyone thought about an agent holding it.

so the number is the first job, and onramping what the number unlocks is the second.

## what an onramp is

an onramp is a plan, in data, for turning "i have a number" into "this rail is open", including the parts that stay human. it is not a lane. the lane lives in the umbrella with its carrier, its gate and its honest state, and it is the thing that answers when somebody writes. the onramp only gets you installed and registered, and then gets out of the way.

```
heyphony get signal                       # the whole plan: install, register or link, verify
heyphony get signal --path link-desktop   # no number needed, one qr scan
heyphony get signal --run                 # execute the install steps
```

dry by default, `--run` when you mean it, and the qr scan stays a person's act, because a linked device is an identity and identities are not self service. recipes are json files rather than code, so a new rail is data, and every command in them was checked against upstream rather than remembered.

## signal, worked through

signal is the best example because it is the least scriptable. there is no bot api to sign up for, no dashboard to click through, and no way to be reached by a program unless somebody holds a number. three paths exist, and they are not equally good:

**phone-signup, the default.** a durable but idle android spawnable signs up with the did as its number. the sms code never reaches a handset because heyphony catches it, and the agent reads it out of the inbox and types it into the phone. the phone becomes the identity of record and can go back to sleep, because owning an account is not a job. then `/v1/qrcodelink` with `device_name=heyphony-desktop` attaches an ordinary desktop as a second device, scanned from the phone. one identity, two devices: the relationship a person has with their laptop.

**link-desktop.** if a phone already owns the account, this is the whole thing: one qr scan and the desktop joins as a secondary device. no number required.

**register-number, the weakest.** register the did directly. signal is far less strict about voip numbers than whatsapp or google, which is an observation rather than a promise, and this path has no device of record and may meet a captcha.

never a second account to get a desktop session. that is the rule the whole page is protecting: an agent that signs up again because logging in was inconvenient has created a person it has to maintain forever.

## the boundary, said once

heyphony onramps signal. it does not become signal. the lane that catches a signal webhook, holds the hmac and answers people lives in the umbrella with every other carrier, and it must, because a carrier is a carrier. what belongs here is the number and the install, since a number is what this folder holds.

the same shape covers whatever comes after signal. anything that says "bring a phone number" instead of "bring an api key" is a candidate, and adding one should mean writing a json recipe, not a new module.

## what an onramp is not

it is not a signup bot. it does not create accounts, solve captchas, or pretend to be a person at a keyboard. it does not click through a dashboard on your behalf, because dashboards are where a provider expects a human and a small amount of friction there is a feature: it is the difference between an agent that has an account and an agent that has farmed one.

it also does not promise that any particular rail will accept a voip number. some will, some will not, some will today and not next month. that uncertainty is recorded in the recipe as `may_be_refused` rather than smoothed over.
