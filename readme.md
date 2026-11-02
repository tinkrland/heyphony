# setup: where the machine holding the number actually lives

*three modes, one question, and the two of them that answer it honestly*

`main` gives you the package and says what it does. this branch is the other half of the sentence: **which computer holds the registration, where the secret sits, and what happens to both when that computer sleeps.** get that wrong and nothing else matters, because a phone number is the one part of a comms stack that has a real world object behind it, and that object is somebody else's switch in somebody else's rack waiting for an answer on a socket you are supposed to keep open.

there are three shapes people actually ask for, and they are not three flavours of the same thing. an agent on a computer you already own, an agent with a computer of its own, and an agent in a body that gets shredded after the job. they cost different amounts, they fail in different places, and only one of them is what most people mean when they say "just put it in a container".

## the three things every mode has to place

before the modes, the nouns, because every mode is just an answer to where each of these lives.

**the registration.** one sip registration, kept alive by a client on a host. a did is *one* registration, not one per machine: a second machine registering the same number is a race, not a second line, and both ends drop calls while they argue about who is current.

**the secret.** the sip username and password, plus whatever provider credentials the hooks need. it is long lived by nature, and it lands in `~/.config/linphone/linphonerc` at mode 0600 because it is a password in a text file.

**the catcher.** the small http listener that receives the provider's text webhook and appends to the inbox. it needs to be reachable from the internet for the fifteen seconds a text is arriving, and the inbox keeps working without it only when the provider has an email fallback.

every mode below is a sentence about where those three sit, and the honest cost of putting them there.

## mode one: an agent on a computer you already have

the cheapest mode by a wide margin, and the only one where the answer starts with a question, which is **which computer**. the number does not care about the machine, but the sip client, the audio path and the thing that keeps the catcher alive all do, and the differences are large enough that a generic "run it locally" instruction is a trap.

the shape is the same everywhere: `heyphony connect` writes the registration on that machine, `heyphony serve` catches, `heyphony status` says what is registered and what arrived. run from a clone or from the one line install, the commands are identical.

### macOS, which is usually a laptop that sleeps

`brew install baresip` gets the client, and heyphony writes its config rather than asking you to hand edit one. the catcher wants a launchd agent so it comes back after a reboot, and the honest limit is the one nobody writes down: **a closed lid is a sleeping machine, so calls do not ring.** texts still arrive, because a provider posts or emails them and neither needs your laptop awake.

the two things to get right on a mac are the microphone permission prompt, which appears once and never again (and if you dismiss it, audio silently records nothing), and the fact that a laptop moving between networks changes its ip, so the provider's webhook url needs a stable name in front of it: a tunnel or a dynamic dns record, not `192.168.x.x`.

### linux, desktop or a box in the corner

`apt install baresip` (or your distro's equivalent) and a `systemd --user` unit for the catcher, which is the least dramatic always-on story of the five computers here: a box that is plugged in and never closed is a box that answers at three in the morning.

a desktop with a sound card can speak and listen. a headless box cannot, and that is the point worth internalising early: **a call is media, so a machine with no audio device can register, dial, and record, and cannot be a speakerphone.** texts and voicemail do not care at all.

### a server you ssh into

the cheapest honest always-on host, and the same caveat as the headless desktop plus one more: opening the catcher's port means opening it to the internet, so the token on the webhook path is doing real work and should be long.

everything works except the microphone. if a rail needs a live voice conversation rather than a recording, this is the wrong mode for that rail and the right mode for every other one.

### windows, through wsl2

the least proven of the five and worth saying plainly rather than dressing up. the cli and the catcher run happily inside wsl2, which is where the inbox, the hooks and the setup live. the sip client is the awkward half: a wsl2 guest has no audio device by default, so audio needs a pulse bridge or a softphone running on the windows side while heyphony owns the config and the inbox.

if the machine is a windows laptop, mode two is often the better answer for the same money and none of the bridging.

### a small always-on box, which is the shape most people actually want

a raspberry pi, a mini pc, an old laptop with the lid taped shut. the number registers, the catcher runs, the box draws four watts, and calls ring at three in the morning. this is the mode that makes "a number of its own" mean something, and it is a one-time purchase rather than a monthly bill.

the cost is that it is a machine in your house, so it is your power bill, your network and your patching. the win is that the secret never leaves a disk you can hold.

## mode two: an agent with a computer of its own

same three nouns, moved off your desk. the reason to do it is that the registration and the catcher keep running when your laptop closes, and the reason to think about it is that **the catcher needs an inbound port and a container on a home connection does not have one.**

### a container on the computer you already have

the container solves the dependency problem and not the network problem, which is the distinction that saves an afternoon. sip registration is *outbound*, so it works fine from behind nat. the text webhook is *inbound*, so it needs a tunnel or a port forward, and that is true whether the catcher runs in docker or on the metal.

two things the container shape has to get right. it wants host networking, because rtp picks a wide port range and mapping it by hand is a losing game. and the state must be a volume, because `~/.config/linphone` and `~/.local/share/telephony` are the registration and the inbox, and a container that loses them loses the number and every message with it.

### a vm in the cloud

the shape that just works, because a public ip solves the inbound half by existing. a single small instance is enough: the catcher is idle, the client is idle, the number is idle, and the meter runs on being reachable rather than on being busy.

the honest costs. there is no audio device, so this host can record a call and cannot hold a conversation without a media rail. the secret sits on somebody else's disk, which is a different trust question from a box in your house and worth answering deliberately rather than by default. and the machine is now part of your patch surface, because an always-on public listener is an always-on public listener.

what you get for it is the thing the whole mode exists for: **calls ring whether or not you are awake**, and the inbox is caught as it arrives rather than on the provider's retry schedule.

### the same shape without the paperwork

a container on a server you already run, with a tunnel in front for the webhook, is a legitimate middle. it is one process tree, one volume, one `restart: always`, and it is the answer for somebody who has a homelab and no interest in a cloud account.

## mode three: an agent using a spawnable

a spawnable guest is a body with a lifecycle: it exists for a job, and then it is shredded. that is the right shape for almost everything an agent does, and it is the **wrong** shape for two of the three nouns, which is why this mode is the one where honesty matters most.

a registration cannot live in a body you are going to burn. the secret would be copied into a lane designed to be destroyed, so it would need re-issuing on every spawn, and worse, a number that only rings while a guest happens to be up is dead in exactly the case the number exists for: idle at three in the morning. the code says the same thing as data, `linphone.connection_plan(did, "guest")` reports `secret_in_burn: true` and `survives_burn: false`, and the default is the other one.

so the shape that works is a split. **the registration and the catcher stay on a durable host**, which can be any mode one or mode two machine, and **the guest reads the inbox over the control plane** and never holds the provider credential. the guest gets what it wants, which is a mailbox it can query without an email client, and the number keeps the property that makes it worth having.

### when the durable host is itself a spawnable

there is a middle that is not a cheat: a duty-cycle guest, which stays registered during its window and sleeps outside it. the number rings during the window, texts arrive always, and the machine costs a fraction of an always-on one. it is honest as long as the schedule is stated, because a caller at the wrong hour gets no answer rather than a lie.

### and the one place a guest registration is right

proving it. `heyphony connect --on guest` exists so a test can show registration from inside a guest, and it reports the liability in its own output rather than hiding it. use it to verify, never to serve.

## which mode is which, in one table

|  | registration survives sleep | calls while asleep | texts while asleep | secret leaves your disk | inbound port needed |
| --- | --- | --- | --- | --- | --- |
| a computer you own | no | no | yes | no | only for the catcher |
| a computer of its own | yes | yes | yes | yes, to the host you rent | only for the catcher, and a public ip answers it by existing |
| a spawnable | only with a duty cycle | only in the window | yes | no, the guest never holds it | no, the durable host carries it |

the column that decides most arguments is the first one. everything else follows from it.

## what every mode shares

the install is one line in all three modes, and it is the same line:

```
curl -fsSL https://raw.githubusercontent.com/tinkrland/heyphony/main/npm/install.sh | sh
```

the did comes from a provider either way, and no mode makes it free: about a dollar a month at the cheap end, and the number is still classified as voip whatever you run behind it. the install is the same command in all three. and two acts stay human in all three, because they are not technical: **paying for the number**, and **fetching the sip password out of a provider dashboard** the first time.

the rest of this branch is a planner rather than a paragraph: `python3 modes.py --compare` prints the table above, and `python3 modes.py --mode local --host macos` prints the exact errand for that pairing, including which of the steps are yours. the readme and the planner are pinned to each other by the tests, so a claim here that stops being true fails the suite instead of aging quietly.
