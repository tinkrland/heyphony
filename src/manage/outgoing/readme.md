# outgoing: what leaves, and what does not

today, nothing leaves. a reply drafted in the launcher is kept and the page says so in the same breath it confirms the draft:

> draft kept, not sent. no outbound api path is wired for this provider

that is deliberate. sending is the part of telephony where a mistake is not a bug, it is a message a real person reads, so the first send rail will be written carefully and not improvised late at night.

## what the rail will be

**sms on this number, paid per message.** the vendor charges for outgoing, which is the whole economic reason this package is inbound first: receiving is cheap or free, sending costs money per message, and a tool that sends on its own is a tool that spends on its own.

**not imessage.** imessage and rcs live in the umbrella (`comms/imessage/`), because they are a different rail with a different free tier and a whitelist, and because a voip did cannot register imessage at all. heyphony owns the number, not the bubbles.

**one message at a time, at human pace.** bulk outbound is refused, not because it cannot be typed but because a2p consent, attested origination and a registered business are the real requirements, and a self-hosted softphone behind a cheap did is the exact shape carriers block first. `theidea/access.md` has the longer version.

## attachments

inbound already handles audio: an attachment with an audio content type, or an audio extension, is written next to the voicemail sidecar and never held only in memory.

outbound has no attachment path, and mms is not supported by any vendor in the table in a way worth pretending about. a link in an sms is the honest substitute, and it is the one that survives a carrier that mangles a picture.

## so what is a draft, mechanically

a draft is a string in the page, with the route to reach the person already resolved (which handle, which channel, which number). the missing half is the send call. when it exists it will be one function with a provider, a did, a recipient and a body, gated the same way the catcher is gated, and it will refuse to send to a number that has not written first unless a human asks for it explicitly.
