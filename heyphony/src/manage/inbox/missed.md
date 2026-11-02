# missed calls

a missed call is a call that arrived, rang, and was not answered. this package reads it out of the sip client's own database instead of maintaining a second call log, because the client already writes one and two logs eventually disagree.

`heyphony open calls --missed` filters to those. the rows come from the `call_history` table, which carries caller, callee, direction, duration, start time and status per call, so a missed call is a status rather than an inference.

two limits worth stating plainly:

- it is read after the fact, so a call appears on the next read rather than while it is ringing.
- on a host with no client running there is no history to read at all, which is the same fact as "calls need a registration", seen from the other side.
