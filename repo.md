# repo

*every branch of this repo, what it holds, and which of them the `mcp` branch already contains*

this repo is one package and several lines of work beside it. `main` is the number and the rails a number unlocks, and everything else is a branch that adds one thing, so the quickest way to know where something lives is to ask whether it is the number or the conversation around it. this page is the index, and it lives on `mcp` because `mcp` is the branch that holds the most of the others.

## `mcp` is the branch that carries the rest

`mcp` is a single flat branch with no `mcp/` folder in it: the server and the sdk sit in `npm/`, the python they call sits at the root, and the lookup, the groups and the inbound allowlist are all in the same tree. it holds fifteen tools, twelve that only read and three that reach outside the machine, and it was built by merging `lookup` and `allow` into the original server so that a tool never calls a verb its own tree does not have.

`main` is deliberately not merged into it the other way round: `main` keeps its readme rule that the word group never appears on the page, and `mcp` narrows that rule to the part above its own mcp section. until that is decided, the two stay apart.

## the branches

| branch | what it holds | already in `mcp` |
| --- | --- | --- |
| `main` | the number, the inbox, the catcher, the send rail, the setup runbook and the npm installable | yes |
| `mcp` | the stdio server, the sdk, the lookup, the groups and the inbound allowlist, as one tree | this is it |
| `lookup` | what a number is from the plan that issued it, handles and addresses beside numbers, and groups as a carrier thread | yes |
| `allow` | the inbound policy: a list, a home country, or chosen countries, closed by default | yes |
| `callheavy` | our own outbound calls arranged around a task, driving baresip over its control socket | no |
| `mobile` | the phone as a device, the host bridge that answers for it, and the ring rail | no |
| `omni` | the rest of the carriers, as lanes beside the number | no |
| `meetings` | joining the room where the humans are | no |
| `setup` | where the machine holding the number lives, as three modes | no |
| `new` | forwarding, and why a call handoff is not a text handoff | no |

the last column is read from git and not typed: `tests/selftest.py` recomputes it for every branch the repo has, so a branch that gets merged in without this page changing fails the suite.

## where a thing goes

- **the number itself, or a rail the number unlocks** goes on `main`, and then reaches `mcp` by merge.
- **a tool an agent can call** goes on `mcp`, and only for a verb the tree already has.
- **a new place for the number to live** goes on `setup`.
- **a conversation that is not a phone call** goes on `omni`, or on `meetings` when it is live.
- **anything that places a call on its own** goes on `callheavy`, which is the only branch allowed to ring somebody, and only with a named authoriser.
