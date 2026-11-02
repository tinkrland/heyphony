# turnedoff: the host is down

the host is off, which is the normal state of a machine that is not needed every second. what happens next is a property of the vendor, and the difference between vendors is large enough that it decided which vendors this package recommends.

| vendor | texts | voicemail | live calls | how |
| --- | --- | --- | --- | --- |
| voip.ms | yes | yes | no | sms to email, carrier side voice to email |
| anveo | yes | yes | no | url forward for sms, carrier voicemail |
| jmp.chat | yes | yes | no | texts and transcribed voicemail as jabber messages |
| flowroute | yes | no | no | http webhook to a proxy that emails; no voicemail fallback |
| signalwire | yes | no | no | webhook only, so it needs something listening |
| questblue | yes | no | no | put to a url, same requirement |
| bulkvs | yes | no | no | webhook, same requirement |
| voyced | no | yes | no | no sms claim at all |
| voxacall | no | no | no | sip trunking only |
| bitcall | no | no | no | no inbound dids yet |

two facts sit under that table and they explain most of the confusion people have about agent phone numbers.

**a text never travels over sip.** it is held by the vendor and posted or emailed, which is why an inbox can outlive a powered off machine and why a softphone has nothing to do with sms.

**a call is sip**, so it needs a registration, and a registration needs a machine that is running. no vendor in the list will answer a call for you and hand you a recording without also being the voicemail product. that is what carrier voicemail is: the vendor answering on your behalf, and only some of them offer it.

the consequence worth designing around: pick a vendor whose texts survive the machine being off, or the number only works while you are awake.
