# glossary

*the words this folder uses, and what they actually mean*

**did**: direct inward dialing, which in practice means "a phone number you rent". a did is a lease on a slice of the numbering plan; you do not own it, you rent it monthly, and it reverts when you stop paying.

**e164**: the plain international form of a number, plus sign and digits, no spaces or punctuation: `+12125551234`. every provider has its own idea of how to format a number and this is the one we store.

**sip**: session initiation protocol, the signalling standard voip runs on. it handles invite, answer, hang up, and agreeing on what the media will be. it does not carry the audio itself.

**rtp**: the protocol that carries the audio. this distinction is the source of most confusion about phones: sip is the doorbell, rtp is the conversation, and they can fail independently.

**pstn**: the public switched telephone network, the one your grandmother's number lives on. the point of a did is that it reaches the pstn from a program.

**trunk**: a bundle of lines between two phone systems, or in the voip era, a credential that lets one system hand calls to another. "trunk provider" means a company that sells wholesale call paths rather than a friendly dashboard.

**registration**: the client telling the provider "i am here, send calls to this address". it expires, so it has to keep happening. this is why a sleeping host does not ring, and why a number registered from two machines is a race rather than a second line.

**softphone**: a phone that is only software. linphone and baresip are the two this folder lives next to.

**pbx**: private branch exchange, the box that owns the extensions inside an office. every feature people call modern telephony was invented on one of these in the nineties.

**codec**: the format the audio is compressed into. both ends must agree on one, which is a real failure mode when two systems disagree about `opus`.

**voip**: voice over ip, and also a *classification*: a number type that carriers and risk engines can see, and that a large share of signup flows refuse. no provider's marketing changes the classification.

**sms-to-email**: a carrier feature that turns an inbound text into an email. crude, ancient, and the single most reliable way to receive a text while the machine is off.

**webhook**: an http request a provider makes when something happens. most of this folder's inbox arrives this way: the provider posts, the catcher stores, nobody had to be awake.

**catcher**: our name for the small http server that receives provider webhooks, checks the token, normalises five different payload shapes into one envelope, and stores them. `heyphony serve`.

**envelope**: the one message shape every lane produces: id, channel, direction, sender, recipient, subject, body, at, thread, reply_to, raw. nine carriers, one object.

**works while off**: the property that decides most of this lane's design. texts and voicemail are provider side and survive a sleeping host; live calls are not and do not.

**onramp**: a plan for turning "i have a number" into "this rail is installed and registered", including the steps that stay human. `heyphony get signal`.

**getter**: the implementation of an onramp: one json recipe per rail, dry by default. a getter is not a lane.

**lane**: a carrier plus a gate plus an honest state, living in the umbrella folder. the thing that actually answers people.

**a2p / 10dlc**: the registered, consented, business-messaging regime that bulk outbound sms lives under. this lane refuses bulk outbound rather than pretending to qualify for it.

**stir/shaken**: the caller id authentication framework carriers use to mark calls as attested. a self-terminated cheap number is the least attested thing on the network, which is why spam filters eat it.

**cnam**: caller id name lookup: the name that appears on the other person's screen. often a paid lookup, sometimes wrong, and never something to rely on for identity.
