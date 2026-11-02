# runner: the cli, and the page

two surfaces, one state. `cli.py` is a set of commands that print json. `gui.py` is a local page with three tabs that reads the same files. neither one owns a fact the other invents.

## the cli, and why it looks like this

every command answers a question an agent can ask in a shell, and prints json so nothing has to be scraped:

```
heyphony setup                     the plan for this host, as data
heyphony setup select sip          the guided walk: vendor, then existing or new
heyphony setup provision           anveo: areas, stock, price, prepared order
heyphony connect sip --voipms      write the config, one registration, on the host
heyphony hooks anveo               the url and setting that makes texts arrive
heyphony serve --port 8099         the catcher: texts and carrier emails land here
heyphony app                       the launcher, on 127.0.0.1:8790
heyphony open messages|calls|voicemail
heyphony get signal                open a rail that wants a number
heyphony doctor                    what is configured, and what is still designed
```

the shape rule is that every menu key is also a flag. a human gets arrow keys, an agent passes `--provider anveo --did +1...`, and a run with no terminal and no flags prints what it needs instead of blocking:

```json
{"needs": "provider", "flag": "--provider", "options": ["voip.ms", "flowroute"]}
```

that one behaviour is the difference between a tool an agent can drive and a tool an agent can only describe to a human.

## install, meaning how it gets on the agent's cli

there is no `heyphony install` command, and that is the honest state of it. the ways it reaches a shell today:

| way | command | what it is good for |
| --- | --- | --- |
| the shim in the repo | `/path/to/spawnables/bin/heyphony status` | zero install, works over ssh, keeps the clone as the source of truth |
| a symlink on path | `ln -s /path/to/spawnables/bin/heyphony ~/.local/bin/heyphony` | the agent types `heyphony ...` like any other tool |
| the module directly | `PYTHONPATH=/path/to/spawnables python3 -m src.runner.cli status` | when there is no bin directory on path at all |

the shim sets `PYTHONPATH` to the clone and execs the module, so nothing is installed in the sense of copied elsewhere and nothing drifts out of date. two things are deliberately missing and should not be pretended into existence: a systemd unit for `serve` and `app`, and a pypi package. a unit is the right answer for a host that should answer texts after a reboot, and it is not written yet.

## the page

`gui.py` serves one html document from the standard library, no build step, three tabs: caught messages, voicemail, calls. it drafts and never sends. when a reply is drafted it says so in the same breath:

> draft kept, not sent. no outbound api path is wired for this provider

`heyphony app --json` answers without serving: it prints the tabs, the counts per tab and who is in the threads, then exits. an agent asking what is in the inbox should not have to background a server and kill it afterwards to find out, which is exactly what a json flag that also blocks would force.

the page exists because a mail client gives a human a stable handle per conversation, an is-it-new answer, and a cheap way to read one item, and an agent gets none of those from a mailbox. it is not a chat app and it does not try to be one.
