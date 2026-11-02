# voip.ms

the provider that keeps catching things while the machine is off.

## three cloud features that outlive the vm

- **voicemail to email.** the carrier records the message and mails it. an idle, paused or powered-off guest still receives it, because the catching happened at the carrier, not on the machine. this is the difference between "my agent missed a call" and "my agent has the audio file".
- **sms to email.** same shape for texts: they land in a mailbox, not in a softphone. sms over sip is not a thing here either, so the mailbox *is* the delivery mechanism.
- **conditional forwarding.** the number can be told to ring the sip registration only while it is registered, then fall through to voicemail or another number. that is a carrier-side rule, so it behaves correctly when the guest is asleep.

calls themselves are still sip: no registration, no ring, unless conditional forwarding catches it first. what differs from flowroute is that the fallback exists and is configured at the provider.

## setup sketch

1. order a did, confirm it is sms-capable for the sub-account you will use
2. enable voicemail to email and sms to email, then confirm with a test message *before* trusting the card
3. set conditional forwarding: registration alive -> sip; otherwise -> voicemail (or another number)
4. `telephony connect linphone --voipms --did ... --username <subaccount> --password ... --server <your server, e.g. atlanta.voip.ms>`

the server matters: voip.ms is regional (`atlanta`, `chicago`, `toronto`, ...) and a wrong server is the classic silent registration failure. `telephony doctor` prints the one you configured so the card can show it.

## the honest limit

voicemail-to-email and sms-to-email are *carrier* features on the owner's account. nothing in this repo can verify they are switched on, so `telephony status` reports them as `unverified` until a message actually arrives. a phone number that has never received a message is not proven to work.
