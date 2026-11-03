# discord

watching and answering in servers. two rules, both learned from prixie's watch
route: one long-lived gateway connection per process, and the credential is the
server's env, never a caller's.

wired: the watch contract (guild events and voice states arrive live; the routes
only read) and the reply path through the bot token.

not wired: anything that speaks unprompted. a channel is treated like a group: the
agent answers when it is addressed, and a watched room opening a call is a signal to
attend, not an invitation to talk.

gate: `DISCORD_BOT_TOKEN`.
