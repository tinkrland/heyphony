# linphone, wrapped

the sip layer is one module because sip is one thing: a registration, a media stream and a call log. everything else in this package asks `sip.py` for a plan and never touches a config file itself.

what it actually does, in the order it does it:

1. **registration plan.** `connection_plan(did, endpoint)` returns one registration and the reason. the default endpoint is the host, because the sip password is a long-lived secret and a burnable guest that holds it needs it re-issued every spawn, while a number that only rings while a guest is up is dead in exactly the idle case that matters.
2. **config it writes.** the module generates `~/.config/heyphony/sip.rc` at mode 0600 from the client's own key names: `proxy_0` with `reg_proxy`, `reg_identity`, `reg_expires`, `realm`, and `auth_info_0` with `username`, `userid`, `passwd`, `realm`, `domain`, `ha1`. those names are read from linphone's source, not remembered.
3. **reads, not writes, for history.** calls come from the client's own sqlite `call_history` table, so the agent reads the truth the client recorded rather than a log this package maintains in parallel.
4. **the host client.** for scripted call control the chosen client is baresip, because `ctrl_tcp` speaks json both ways (`{"command":"dial"}` in, json events out), which is the only requirement worth having here. the verdict lives in `sip.py` as data with the reasoning attached, so it does not get relitigated from vibes in six months.

what is not here: a headless console for linphone. linphone ships a desktop application and an ipc surface, not a scriptable console, so call control does not go through it.
