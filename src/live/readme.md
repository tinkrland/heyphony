# live

one number carries two things at once, and this module is the program that holds both.

a text never arrives over sip and a call never arrives over http, so at the carrier they are two
different deliveries to the same number. the reason this needs code rather than a shrug is that an
agent is one process with one attention span: while it is talking it still has to notice that the
person said "hold on, i just sent a screenshot", and it has to be able to say which of the two
happened first.

## the three facts that make it work

**two doors, no queue.** the invite arrives on the socket `baresip` already owns (`ctrl_tcp`), and
the text arrives as an http post to the catcher. the catcher used to be a single thread, which meant
one slow carrier could hold the door shut while a call was up, so it is a `ThreadingHTTPServer` now
and the sip socket is read in its own loop. neither rail waits for the other, and a test makes the
store slow to prove it.

**one log, sequenced.** `Timeline` is an append-only list with a lock and a sequence number. two
rails writing two files is the shape that makes an agent answer a text that arrived before it heard
the sentence. one log means `answered -> text -> hung up` is a claim you can check rather than
reconstruct.

**a wait that watches both.** `Timeline.next_event(since, rails, timeout)` blocks on a condition and
returns the first event from either rail, so the agent's loop is woken by whichever spoke. polling
each rail on a timer is the version that misses the thing said mid-sentence.

## what it costs and what it refuses

the audio is still `baresip`'s: this module holds the call, it does not bridge it to a room and it
does not transcribe it. those stay named as not shipped, in `plan()`, where a reader will find them
before believing otherwise.

`Session.start()` connects the sip socket and opens the webhook. a socket that will not connect is
recorded as `no sip socket` rather than raised, because the text rail working while the call rail is
down is a real state and one an agent should see rather than crash on.

## proof, and the part that is not proof

proven in the suite: a text lands between "answered" and "hung up" on a call, both rails run at once
without blocking, a refused sender still reaches the log, an answer goes out over the same socket as
one netstring command, and the protocol reader tolerates netstrings, bare json and a read split in
half.

not proven: a registration at a carrier, and a carrier's own mms on a live call. the first honest run
of that is one number, one person, one call, one picture. until it happens the claim here is about
this software, not about the carrier.

## the picture itself

an mms is a text plus urls on the carrier's host. `src/manage/media.py` fetches one under an 8 MB cap
and names the file for its content type, refusing a non-http url, an oversize file and a type that is
not a picture or a voice note. fetching a jpeg is not describing it: the reading is the caller's job,
and a url behind the account's login answers 401 and says so.
