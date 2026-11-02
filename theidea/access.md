# access

*how you get this, what it will be licensed under, and what does not exist yet*

## today: turnkey, on your own machine

right now access means: take the folder, put it on a host, give it a number. `heyphony setup` prints the whole plan as json, `heyphony setup select sip` walks it, and the provider hooks are printed per provider. nothing is hosted by us and nothing phones home. the number is yours, the credential is on your host, the inbox is a jsonl file in your home directory.

that will stay true. whatever else changes, the self-hosted path does not become a second class citizen, because the reason this exists is that a number should belong to the machine its owner controls.

## open source, with a licence question we have not closed

the intent is to publish this openly. the specific licence is **undecided**, and the reason it is undecided is not laziness, it is that there are two defensible answers and one real constraint.

the constraint: **linphone is copyleft.** its desktop client is gpl-3.0 and the sdk is agpl-3.0. this folder does not link against linphone; it generates a config file in the format linphone reads, and separately allows a client to be run on the host. whether that counts as "using linphone" in a way that reaches this code is exactly the question a licence decision has to answer, and the honest position is that we are not sure yet and will not guess.

the three candidates:

- **agpl-3.0**, which is what we get for free if we ship anything that is a derivative of linphone's sdk, and which some people will refuse to run. if we adopt something like the stock linphone cli as part of the code path, this is the low-risk answer.
- **bsl 1.1**, which would let the source be readable and self-hosting stay free while a managed service is a commercial conversation. the shape we are considering is the usual one: to third parties offering this as a hosted or managed cloud service, either (1) you have a separate commercial agreement with the author, or (2) you modify the software *and* make the complete source of your modifications, together with the entire hosting infrastructure, management and billing stack used to run the service, publicly available under an open-source licence. time-boxed, converting to an open licence after the change date.
- **fsl 1.1**, which is similar in spirit to bsl and stricter about competing services, and which fits if the thing we actually care about is "you may run this, you may not resell it as a product".

which one wins depends on the linphone question, and possibly on which linphone surface ends up in the code path: the cli (agpl-3.0) and the desktop client (gpl-3.0) are not the same obligation. expect this page to change with the answer rather than quietly resolving itself. it is not legal advice and it is not a commitment, it is a decision that has been left visibly open on purpose.

## planned, and in this order

- **api**: the cli is already json, so an http surface is mostly transport: plan, provision (up to the money step), hooks, open, and a webhook catcher per provider.
- **mcp server**: the same verbs as tools, so an agent can hold a number without shelling out. the cli flags were designed for this already; every menu choice is a flag because a model cannot click.
- **npm installable package**: `npx heyphony` for the setup and hook side, for people whose agents live in node and who will never open a terminal twice. the python package stays canonical; this is a shipping decision, not a fork.
- **cloud hosted**: someday, idk. if it exists it is the bsl/fsl conversation above made concrete, and it will be a boring hosted version of the same cli rather than a different product.

none of the four changes the shape of what is here: the number is a registration, the inbox is a file, and the catcher is a small server. hosting those is easy. refusing to become a dashboard is the part worth writing down.
