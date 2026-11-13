# src

everything that runs, in the folder that names what it is for. the modules here are imported, the sibling folders describe, and `../directory.md` holds the map that connects them.

```
src/
  providers.py   the vendor table: price, text style, what works while the machine is off
  runner/        cli and launcher
  linphone/      the sip client, wrapped so the rest of the code never touches a config file
  setup/         no number yet, and then a number that answers
  manage/        the number answering, for as long as you keep it
  lookup/        what a number is, from the plan that issued it, without messaging anybody
  live/          a call and a text arriving at once, on one number and in one program
  callheavy/     a call placed on purpose, and the agent's ears and mouth on it
  onramp/        rails that want a phone number before they will talk to you
```

`live/` is the only folder that is a pair: the call socket and the text webhook are two deliveries to one did, and the reason they are one module is that the ordering between them is the question.

the split is by lifetime, not by technology. `setup/` is work you do once per number and then never again. `manage/` is what runs every day after, which is where the agent actually lives. `onramp/` is opt in and stays opt in: a rail is opened deliberately, by name, with `heyphony get`.

`providers.py` sits at the root of `src` because four folders read it and it owns nothing. a design rule that came out of that: vendor facts are data, so a new vendor is a dict entry and never a new branch in a command.
