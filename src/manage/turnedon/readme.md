# turnedon: the host is up

the host is running, so both halves of a number are live.

**texts** arrive as a post to the catcher (`heyphony serve`, default port 8099) on `/sms/<vendor>`, are normalized into one envelope, deduplicated by the provider's id, and appended to the inbox. the catcher answers 403 to a sender that is not whitelisted and 403 to a wrong secret, so an open port is not an open mailbox.

**calls** ring the sip client registered on this host. one registration, because a did is one registration and a second machine claiming it is a race rather than a second line. a call that is not answered becomes a voicemail file if the vendor offers carrier side voicemail, which is a property of the vendor and not of this package.

**missed calls** come out of the client's own call history table afterwards, not from a live event, which means a call shows up on the next `heyphony open calls` rather than while it is ringing.

what the host being up buys you, precisely:

| thing | while up | note |
| --- | --- | --- |
| texts | posted in seconds | needs the catcher running and the hook armed |
| calls | ring | needs the registration, which is on this host by default |
| voicemail | recorded, then a file | the file is written where `views.py` reads |
| transcripts | only if the vendor transcribes | this package will not invent text from audio |

one honesty note sits at the bottom of this page in every other form too: nothing here has placed or received a real call yet. the lane is configured and the routing is documented, which is not the same claim.
