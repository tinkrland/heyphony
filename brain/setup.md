# setup: pointing a brain at this number

this runbook is short because the work is short, and the only real decision is which of the four
shapes fits what you already have. the rest is one command per step, and every command prints what it
would do before it does it.

## 1. pick the shape you already have

do not install anything to answer this. the brain you want is almost certainly the thing you were
already talking to.

| if you have | use | because |
| --- | --- | --- |
| a claude subscription and the `claude` cli | `--brain claude` | its login is already done, and `-p` is a one-shot answer |
| a codex login and the `codex` cli | `--brain codex` | `exec` is the non-interactive verb |
| an api key, or a server that speaks chat completions | `--brain openai` | the base url is an env var, so a local server is the same path |
| a script that reads stdin and writes stdout | `--brain shell` | the escape hatch, and the only one whose prompt never touches argv |

`bin/brain adapters` answers this for the machine in front of you and names what is missing, per row.

## 2. prove it answers before letting it near a message

```
bin/brain hello --brain claude
```

one call, one question, and the expected answer is the word `READY`. this separates two facts that
are easy to confuse: *the binary is installed* and *the brain answers*. an answer that is not READY is
still an answer, and the payload prints it rather than summarising.

## 3. read one turn before running one

```
bin/brain plan --brain claude --id <a stored message id> --to +1555…
```

the payload is the prompt the brain will see, the command it will run (or the request it will make),
and the decision that will be applied to the answer. nothing is spent. this is where you find out that
the prompt says `from:` and not a name, which is deliberate: a brain inventing rapport with a stranger
is worse than a brain that is plainly a message from a number.

## 4. open the gate, or do not

the default is a draft. `HEYPHONY_SEND=allowed` is the sentence that lets a reply leave, and it belongs
in the environment of the run rather than in a config file, because a gate that survives a restart is
a gate somebody forgot they opened.

```
HEYPHONY_SEND=allowed bin/brain run --brain claude --id <id> --to +1555…
```

## when it does not work

| what you see | what it means |
| --- | --- |
| `missing: ["claude"]` | the binary is not on `PATH` for this shell. nothing was asked and nothing was spent |
| `missing: ["OPENAI_API_KEY"]` | the http brain needs a key in the environment. it is never passed as an argument |
| `the endpoint answered 401` | the key reached the endpoint and was refused: wrong key, wrong base url, or a proxy eating the header |
| `the endpoint answered something that is not json` | usually an html error page from a proxy in front of the endpoint: read the first bytes, they name it |
| `the reply has no choices` | the shape was nearly right, which usually means a different api version at that base url |
| `the brain did not answer within 120s` | a cli brain waiting on a prompt of its own. check it runs once by hand, without `bin/brain` |

## what this runbook does not cover

sending. the reply leaves through the number's own rail, which lives on `mcp`, and the gate that
guards it is `HEYPHONY_SEND`. if a draft is the output you keep getting, that is the gate working
rather than a bug in the brain.
