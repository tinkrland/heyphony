# brain

*point the agent you already pay for at a number that can reach people*

this branch is the adapter layer, and it exists because the hardest part of giving an agent a phone is
not the phone. `mcp` already delivers a text as a stored message and a call as something an agent can
pick up, and none of that cares what does the thinking. so the thinking is borrowed: claude code,
codex, any endpoint that speaks the chat completions shape, or a command of your own that reads a
prompt on stdin. four shapes, one contract, and two decisions that stay with a person.

the page lives here rather than at the root on purpose: the root page is the number's argument, and
this is one way to use it.

## what the plug actually is

a brain receives one prompt per arrival and answers with text. that is the whole interface, and it is
deliberately smaller than a framework: no tool list, no memory, no loop, no planner. the rails around
it are already built and already tested, and a brain that needs to drive a machine is a different
project with a different threat model.

every adapter answers the same four questions, which is why they can share one turn:

- **where the prompt goes**: on `argv`, down `stdin`, or in a json body.
- **where the answer comes from**: stdout, or `choices[0].message.content`.
- **what proves it is present**: a binary on `PATH`, or a key in the environment.
- **what it never receives from us**: a secret, a carrier payload, or a history it did not ask for.

| brain | what it is | the prompt arrives | what proves it is there |
| --- | --- | --- | --- |
| `claude` | claude code, the cli a person already has | `argv` | the binary on `PATH`, and its own login |
| `codex` | openai's codex cli, in its non-interactive exec mode | `argv` | the binary on `PATH`, and its own login |
| `openai` | any endpoint that speaks the chat completions shape | json body | `OPENAI_API_KEY`, sent as a bearer header |
| `shell` | any command that reads a prompt on stdin and writes an answer on stdout | `stdin` | `HEYPHONY_BRAIN_CMD` |

`bin/brain adapters` prints that table for the machine you are on, with the gaps filled in per row:
which binary is missing, which variable is unset. it spends nothing, which is why it is the first verb.

## the turn, and the two decisions that are not the model's

one arrival makes one turn. the stored envelope is reduced to four fields (`from`, `at`, `body`,
`channel`) and the carrier's raw payload stays behind, because a brain answering a text does not need
the header soup and a text is not an audition for a transcript.

then the answer meets two rules that a brain is never consulted about:

- **`DROP` means drop.** a brain that says it has nothing to add is obeyed. silence is a valid answer
  to a text, and an agent that always replies is a worse correspondent than one that sometimes does not.
- **a shut gate drafts.** the reply is composed and stored as a draft unless `HEYPHONY_SEND=allowed`
  is set. this is the same gate the rest of the package uses, and it is the one thing in this branch
  that can put a message on somebody's phone.

the order is read, then plan, then one cheap proof, then the real thing:

```
bin/brain adapters                      # what this host could run, and what it lacks
bin/brain plan   --brain claude --id …  # the prompt, the command, the request, and the gate decision
bin/brain hello  --brain openai         # exactly one call, asking for the word READY
bin/brain run    --brain claude --id … --to +1…   # the turn
```

`plan` and `adapters` and `refused` never spend. `hello` spends one call and proves reachability
rather than judgement. `run` is the only verb that can produce a message, and only when the gate was
opened by a person.

## a key is never an argument

a command line is readable by every process on the machine, and a shell history is readable by whoever
picks up the laptop. so no adapter is handed a credential through `argv`: a cli brain reads its own
login, the http brain reads `OPENAI_API_KEY` from the environment at the moment of the call, and the
command `shell` runs is whatever that command already had. anything that looks like a key inside a
built command is redacted before it is printed, and there is a test that pastes a key into an argv and
watches it come back as `<redacted>`.

## the base url is a variable because that is the point

`openai` is not "call openai". it is "call whatever answers at this base url", and the default happens
to be the vendor. a local llama server, a proxy that logs, a different vendor with a compatible face:
all the same code path, one env var. the model is `HEYPHONY_BRAIN_MODEL` for the same reason, defaulting
to something small and cheap rather than something clever and expensive.

## what this branch refuses to ask a brain to do

- **answer a call as the person who owns the number**, without saying what it is. a caller deserves to
  know they reached a program, and the first turn says so.
- **send without the gate**: a brain drafts, and a person opens the gate.
- **hold a key**: the key lives in the environment of the turn, never on the command line.
- **remember across turns by default**: a number is not a memory, and this branch keeps no store. if
  an agent needs history, that is a database with a policy, not a side effect of a text arriving.

each of those is one line in `adapters.REFUSED` and one line on this page, and `bin/brain refused`
prints them, because a refusal that only lives in a readme is a preference rather than a boundary.

## state

every adapter is `built`: the command or request is constructed, the answer is parsed, and the
decision is the same one for all four, and the suite drives each of them against a stub. none is
`verified`, because verified means a real brain answered a real arrival on a real number, and that has
not happened from here.
