# setup

one command, one question. `bin/mobile --setup` answers the branch in a single json object, and every
subcommand is one of the areas that object names. nothing here prompts, because the caller is a process.

```
git checkout mobile
bin/mobile --setup      # the branch, the human acts, the areas, the ladder
bin/mobile prove        # the ladder with argv, in the order that fails cheapest first
```

## before anything: the phone is somebody's

four acts are the owner's by nature, and each one is in the plan as `from_owner` with the reason beside
it:

1. connect the phone and accept the debugging prompt. an unauthorized device refuses every verb.
2. unlock the phone and leave it awake. a locked screen is not a broken verb, it is a sleeping phone.
3. sign into the app the phone has to carry. installing is ours, an account and its verification are not.
4. be present for a check that wants a face or a camera. the four verbs are taps and typing.

## the ladder

cheapest failure first, and nothing above a step is required to attempt the step below it:

| step | how | passes when |
| --- | --- | --- |
| one authorized device | `adb devices` | the word after the serial is `device` |
| open a stock app | `adb shell monkey -p <pkg> ...` | the app comes to the front |
| take one frame | `adb exec-out screencap -p` | a png comes back |
| dump the accessibility tree | `adb shell uiautomator dump` then `cat` | the xml has nodes with text |
| tap a label out of that dump | `plan('tap_text', label=..., xml_text=...)` | the label's centre gets tapped |
| type into what has focus | `adb shell input text` | the field holds the text |
| the same look on an iphone | `screencapture -x frame.png` | a frame comes back, and only a frame |

android first because it answers all four verbs. the iphone step comes last because mirroring gives
pixels and nothing to press, so it proves a camera rather than a hand.

## when a step does not pass

**`unauthorized` in `adb devices`.** nobody has tapped allow on the phone yet, and no amount of retrying
changes that. unplug, replug, tap allow.

**an empty dump.** the phone is locked, or it has no writable storage for `/sdcard/window_dump.xml`. the
two look identical from here, so check the screen before checking the parser.

**text that goes nowhere.** nothing had focus. `input text` types into whatever is focused and reports
success either way.

**a dead mirroring window.** the iphone locked. unlocking pauses mirroring, which is a real limit of the
road and not a bug in the step.

**a black frame from `screencapture`.** the wrong window, or a macos screen recording permission that has
not been granted to whatever is running the command.

## who answers, once it rings

waking the panel and being in the conversation are different problems. `bin/mobile answer` lists the three shapes and what the agent actually gets in each: the host softphone (ears, and the phone is not in the call), the phone tapping answer (ringing solved, audio in the handset and out of reach), and an app we ship that joins a room (ears, and a client to build and keep). until that client exists the host is the callee and the phone is the device.

## where the number goes

`bin/mobile routes` is the decision, and the short version is that the host keeps the password. the phone
is needed for the device checks and never for the ringing, so the recommended route leaves the did
registered where it already is.

if an app on the phone has to register the did itself, then the host stops registering first: one did is
one registration, and two machines holding it is a race with a caller on the losing end.

## what is not here

a camera flow, a face check, or a signed hardware verdict from a guest. the first two want a person and
the third is the attack this branch refuses to build. `bin/mobile checks` says which device checks a guest
phone fails, which is the entire reason a phone we hold is in this story.

nothing on this branch is `verified` yet. the word is reserved for a phone we own answering the first two
steps of the ladder, and `bin/mobile --setup` reports an empty `verified` list until then.

## whether it rings while nobody is looking

`bin/mobile wake` answers the question the ladder cannot: a registration is not a ring. android parks the app's network in doze and lights the panel only if the invite lands, an iphone drops the socket when the screen locks and rings through pushkit and callkit if it rings at all, and the carrier's own forward to the phone's number always rings because a person picks up instead of the agent.
