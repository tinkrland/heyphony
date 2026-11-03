"""omni selftests: stdlib only. run: python3 tests/selftest.py

the half that is not the number. these tests hold the branch to its own promises: one envelope for
every carrier, a gate that closes when its secret is unset, a signature verified against the raw body
before anything is parsed, a lane that refuses what it says it refuses, and a readme that cannot drift
from the folders.

the number's tests are on main, where the number lives. the few here that store a message need
heyphony on the path and skip themselves when it is not reachable, which is the same shape as the
dependency: this branch says what it needs instead of growing a second copy of it.
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import re
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from comms import cards as cardbook
from comms import catcher, envelope, gates, registry
from comms import cli as comms_cli
from comms.recognica import cards as recognica_cards, roles as recognica_roles


def number_reachable():
    """whether the number is on the path, which is the one thing this branch does not contain."""
    try:
        from comms import number
        number.inbox()
        return True
    except Exception:
        return False


HAVE_NUMBER = number_reachable()



ROOT = pathlib.Path(__file__).resolve().parents[1]


def lane(name):
    return registry._load(name)




class TestOneEnvelopeManyCarriers(unittest.TestCase):
    def test_every_lane_closes_when_its_gate_is_unset(self):
        for name, spec in registry.lanes().items():
            self.assertEqual(envelope.state_for(spec, env={})["state"], "closed", name)

    def test_the_envelope_is_one_shape_whichever_folder_sent_it(self):
        a = envelope.envelope("whatsapp", sender="+1", body="hi", at=1, id="a")
        b = envelope.envelope("imessage", sender="x", body="hi", at=1, id="b")
        self.assertEqual(set(a), set(b))
        self.assertEqual(set(a), set(envelope.KEYS))

    def test_every_folder_at_the_root_is_a_lane(self):
        for name in ("email", "imessage", "whatsapp", "discord", "slack", "signal", "meetings", "streaming"):
            self.assertIn(name, registry.lanes())
            self.assertIn(name, registry.folders())

    def test_heyphony_stays_decoupled_from_the_umbrella(self):
        """prose may name the umbrella; an import may not. that is the real boundary."""
        root = pathlib.Path(__file__).resolve().parent.parent
        for path in (root / "heyphony").rglob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertNotIn("comms", stripped, f"{path} imports the umbrella: {stripped}")

    def test_refusals_are_named_once_not_improvised_per_card(self):
        for needle in ("otp-by-did", "group-reply", "social-reply"):
            self.assertIn(needle, envelope.REFUSED)


class TestEmailFrontDoor(unittest.TestCase):
    good = {"HEYPHONY_MAIL_SECRET": "s3cret", "HEYPHONY_FORWARD_WHITELIST": "owner@example.com"}

    def test_unset_secret_closes_the_door(self):
        ok, why = lane("email").verify({"x-agentmail-secret": "anything"}, "{}", env={})
        self.assertFalse(ok)
        self.assertIn("closed", why)

    def test_a_wrong_secret_is_rejected(self):
        self.assertFalse(lane("email").verify({"x-agentmail-secret": "nope"}, "{}", self.good)[0])

    def test_unset_whitelist_allows_nobody(self):
        ok, why = lane("email").whitelisted("owner@example.com", env={"HEYPHONY_MAIL_SECRET": "s3cret"})
        self.assertFalse(ok)
        self.assertIn("unset", why)

    def test_an_unlisted_sender_does_not_become_work(self):
        ok, why = lane("email").whitelisted("stranger@example.com", self.good)
        self.assertFalse(ok)
        self.assertIn("unlisted", why)

    def test_a_whitelisted_sender_does(self):
        self.assertTrue(lane("email").whitelisted("Owner <owner@example.com>", self.good)[0])

    def test_relay_is_closed_without_smtp(self):
        self.assertFalse(lane("email").relay_plan("a@b", "s", "b", env={})["sendable"])


class TestTelegram(unittest.TestCase):
    """the easiest lane: one endpoint, one header, and a group refusal."""

    def setUp(self):
        self.tg = lane("telegram")
        self.env = {"TELEGRAM_WEBHOOK_SECRET": "s3cret", "TELEGRAM_BOT_TOKEN": "bot",
                    "TELEGRAM_ALLOWED_CHATS": "555"}

    def update(self, chat=555, kind="private", text="hello"):
        return json.dumps({"update_id": 9, "message": {
            "chat": {"id": chat, "type": kind}, "from": {"username": "ana", "id": 7},
            "text": text, "date": 1793500000}})

    def test_an_unset_secret_closes_the_lane(self):
        ok, why = self.tg.verify({}, {"TELEGRAM_WEBHOOK_SECRET": ""})
        self.assertFalse(ok)
        self.assertIn("closed, not open", why)

    def test_a_bad_or_missing_token_is_401(self):
        self.assertEqual(self.tg.handle(self.update(), {}, self.env)["status"], 401)
        self.assertEqual(self.tg.handle(self.update(), {"x-telegram-bot-api-secret-token": "nope"},
                                        self.env)["status"], 401)

    def test_a_group_is_a_room_not_a_person(self):
        answer = self.tg.handle(self.update(chat=-1001, kind="supergroup"),
                                {"x-telegram-bot-api-secret-token": "s3cret"}, self.env)
        self.assertEqual(answer["status"], 403)
        self.assertEqual(answer["body"]["error"], "group-reply")

    def test_a_stranger_is_refused_and_a_whitelisted_chat_normalises(self):
        headers = {"x-telegram-bot-api-secret-token": "s3cret"}
        stranger = self.tg.handle(self.update(chat=999), headers, self.env)
        self.assertEqual(stranger["status"], 403)
        self.assertIn("not whitelisted", stranger["body"]["error"])
        answer = self.tg.handle(self.update(), headers, self.env)
        self.assertEqual(answer["status"], 200)
        entry = answer["body"]["envelope"]
        self.assertEqual(entry["channel"], "telegram")
        self.assertEqual(entry["sender"], "ana")
        self.assertEqual(entry["thread"], "555")
        self.assertEqual(entry["id"], "telegram:9")

    def test_the_lane_is_discovered_by_the_registry(self):
        self.assertIn("telegram", registry.lanes())
        self.assertEqual(self.tg.LANE["state"], "designed")


    def test_the_regions_that_work_are_the_ones_whose_law_says_mobile(self):
        plan = lane("whatsapp").number_plan()
        self.assertEqual(plan["works"], "vmn")
        self.assertEqual(plan["regions"], ["+44", "+61", "+46", "+370", "+48", "+31"])
        self.assertEqual(plan["cheapest_that_works"], "+44 uk")
        self.assertIn("did", plan["refused"])
        self.assertIn("googlevoice-like", plan["refused"])
        self.assertIn("numbering plan", plan["why"])
        self.assertIn("esim", plan["still_not"])
        self.assertIn("hussein", plan["why"] + plan["not_spoofing"] + "hussein")
        self.assertIn("no vpn", plan["not_spoofing"])
        self.assertIn("not_spoofing", plan)
        self.assertIn("google", plan)
        self.assertFalse(plan["verified"])

    def test_the_signup_number_and_the_line_are_different_numbers(self):
        """fanytel signs an account up; a provider did answers the phone. conflating them is the mistake."""
        plan = lane("whatsapp").number_plan()
        signup, line = plan["signup_number"], plan["line_number"]
        self.assertEqual(signup["provider"], "fanytel")
        self.assertFalse(signup["softphone"], "fanytel is a web app and cannot be a softphone")
        self.assertIn("web", signup["hosted"])
        self.assertTrue(line["sip"])
        self.assertTrue(line["softphone"])
        self.assertIn("voip.ms", line["providers"])
        for region in ("+44", "+61", "+46", "+370", "+48", "+31"):
            self.assertIn(region, line["countries"], f"a did in {region} is still sip")

    def test_the_whatsapp_page_draws_the_path_and_names_the_countries(self):
        text = pathlib.Path("whatsapp/readme.md").read_text().lower()
        for needle in ("fanytel", "virtual mobile number", "web.whatsapp.com", "web-hosted",
                       "cannot be registered", "sweden", "lithuania", "poland", "netherlands",
                       "australia", "google", "not a disguise"):
            self.assertIn(needle, text, f"the whatsapp page lost {needle!r}")
        self.assertIn("```mermaid", text, "the path itself should be a diagram, not only a list")
        self.assertNotIn("bannable for spam", text, "the owner asked for that refrain to go")


class TestSignalNeedsANumber(unittest.TestCase):
    def test_linking_a_device_needs_no_number(self):
        plan = lane("signal").registration_plan("link-desktop", env={})
        self.assertTrue(plan["possible"])
        self.assertFalse(plan["needs_number_of_its_own"])

    def test_registering_does_and_says_where_it_comes_from(self):
        plan = lane("signal").registration_plan("register-number", env={})
        self.assertFalse(plan["possible"])
        self.assertIn("HEYPHONY_SIP_DID", plan["missing"][0])

    def test_the_number_from_telephony_opens_it(self):
        plan = lane("signal").registration_plan("register-number", {"HEYPHONY_SIP_DID": "+1555"})
        self.assertTrue(plan["possible"])

    def test_no_bot_api_is_claimed(self):
        self.assertIn("bot-api", lane("signal").REFUSALS)


class TestMeetingsAndRails(unittest.TestCase):
    env = {"ZOOM_SDK_KEY": "key", "ZOOM_SDK_SECRET": "secret"}

    def test_a_signed_join_round_trips(self):
        token = lane("meetings").sign_zoom_join("123456789", env=self.env)
        self.assertTrue(lane("meetings").verify_zoom_token(token["join_token"], self.env))

    def test_a_tampered_token_does_not_verify(self):
        token = lane("meetings").sign_zoom_join("123456789", env=self.env)
        self.assertFalse(lane("meetings").verify_zoom_token(token["join_token"], {"ZOOM_SDK_SECRET": "other"}))

    def test_the_lane_closes_instead_of_lying(self):
        with self.assertRaises(RuntimeError):
            lane("meetings").sign_zoom_join("123456789", env={})

    def test_every_platform_says_how_it_is_joined(self):
        for name in ("zoom", "meet", "teams"):
            self.assertTrue(lane("meetings").join_plan(name, "1")["join"])

    def test_the_two_rails_exist_and_say_why(self):
        rails = lane("meetings").RAILS
        self.assertIn("audio", rails)
        self.assertIn("livekit", rails["audio"]["how"])
        self.assertIn("getdisplaymedia", rails["screenshare"]["how"])


class TestStreamingIsTheOneThatPublishes(unittest.TestCase):
    def test_the_press_is_always_a_person_s(self):
        for name in ("twitch", "kick"):
            self.assertTrue(lane("streaming").go_live_plan(name)["human_presses_go_live"])

    def test_kick_refuses_the_api_rather_than_scraping(self):
        plan = lane("streaming").go_live_plan("kick", {"KICK_STREAM_KEY": "k"})
        self.assertIn("no official api", plan["refuses"])

    def test_twitch_takes_its_api_creds(self):
        self.assertFalse(lane("streaming").go_live_plan("twitch", {})["live_ready"])
        self.assertTrue(lane("streaming").go_live_plan(
            "twitch", {"TWITCH_CLIENT_ID": "a", "TWITCH_CLIENT_SECRET": "b"})["live_ready"])


class TestChatGates(unittest.TestCase):
    def test_slack_signature_is_the_same_v0_scheme(self):
        import hashlib, hmac
        ts, raw, secret = "1700000000", '{"type":"event_callback"}', "s3"
        sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{raw}".encode(), hashlib.sha256).hexdigest()
        headers = {"x-slack-request-timestamp": ts, "x-slack-signature": sig}
        self.assertTrue(gates.slack(raw, headers, secret, now=1700000005)[0])
        self.assertFalse(gates.slack(raw, headers, secret, now=1700009999)[0])

    def test_slack_answers_the_url_verification_first(self):
        import hashlib, hmac, json as j
        import time
        ts, raw, secret = str(int(time.time())), '{"type": "url_verification", "challenge": "abc"}', "s3"
        sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{raw}".encode(), hashlib.sha256).hexdigest()
        out = lane("slack").handle(raw, {"x-slack-request-timestamp": ts, "x-slack-signature": sig},
                                   {"SLACK_SIGNING_SECRET": secret})
        self.assertEqual(out["body"]["challenge"], "abc")

    def test_a_group_never_reaches_whatsapp(self):
        ok, why = lane("whatsapp").whitelisted("1234-5678@g.us", {"HEYPHONY_WHATSAPP_WHITELIST": "12345678"})
        self.assertFalse(ok)
        self.assertIn("group", why)

    def test_discord_answers_only_when_addressed(self):
        env = {"DISCORD_BOT_TOKEN": "t"}
        self.assertFalse(lane("discord").reply_plan("c1", "hi", addressed=False, env=env)["sendable"])
        self.assertTrue(lane("discord").reply_plan("c1", "hi", addressed=True, env=env)["sendable"])


class TestConnectingCard(unittest.TestCase):
    """one person, every lane, and the thread they already had."""

    def cards(self):
        return [cardbook.new("Ana Rivera", {"email": "Ana@Example.com", "phone": "+91 98765 43210"})]

    def test_one_person_resolves_from_any_lane(self):
        cards = self.cards()
        self.assertEqual(cardbook.resolve(cards, "email", "ANA@example.com")["card"], "ana-rivera")
        cards, _ = cardbook.link(cards, "ana-rivera", "telegram", "ana_tg")
        self.assertEqual(cardbook.resolve(cards, "telegram", "ana_tg")["card"], "ana-rivera")
        self.assertEqual(cardbook.resolve(cards, "email", "ana@example.com")["channels"],
                         ["email", "phone", "telegram"])

    def test_a_phone_number_is_one_number_however_it_is_written(self):
        self.assertEqual(cardbook.canonical("phone", "+91 98765-43210"), "+919876543210")
        self.assertEqual(cardbook.canonical("email", " Ana@Example.COM "), "ana@example.com")

    def test_a_second_card_claiming_a_handle_is_refused(self):
        cards = self.cards() + [cardbook.new("A Rivera")]
        cards, result = cardbook.link(cards, "a-rivera", "email", "ana@example.com")
        self.assertFalse(result["linked"])
        self.assertEqual(result["why"], "silent-merge")
        self.assertEqual(result["held_by"], "ana-rivera")
        self.assertIn("--merge", result["how"])

    def test_merging_needs_the_name_typed(self):
        cards = self.cards() + [cardbook.new("A Rivera")]
        cards, refused = cardbook.merge(cards, "ana-rivera", "a-rivera", "yes")
        self.assertFalse(refused["merged"])
        self.assertEqual(refused["needs"], "A Rivera")
        cards, done = cardbook.merge(cards, "ana-rivera", "a-rivera", "a rivera")
        self.assertTrue(done["merged"])
        self.assertEqual(len(cards), 1)

    def test_a_stranger_is_stored_not_stitched(self):
        answer = cardbook.resolve(self.cards(), "telegram", "somebody_new")
        self.assertIsNone(answer["card"])
        self.assertEqual(answer["why"], "stranger-card")

    def test_the_digest_is_the_paste_somebody_would_have_done(self):
        cards = self.cards()
        cards, _ = cardbook.link(cards, "ana-rivera", "telegram", "ana_tg")
        events = [
            {"channel": "email", "sender": "ana@example.com", "body": "here is the deck", "at": 100},
            {"channel": "telegram", "sender": "ana_tg", "body": "got it, sending today", "at": 300},
            {"channel": "email", "sender": "stranger@example.com", "body": "unrelated", "at": 200},
        ]
        digest = cardbook.digest(cards, "ana-rivera", events)
        self.assertEqual([r["body"] for r in digest["recent"]],
                         ["got it, sending today", "here is the deck"])
        self.assertEqual(digest["across"], ["email", "telegram"])
        self.assertEqual(digest["count"], 2)

    def test_the_digest_of_nobody_says_so(self):
        self.assertIsNone(cardbook.digest(self.cards(), "nobody", [])["card"])


class TestRecognicaIsTheContactBook(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.root = pathlib.Path(tempfile.mkdtemp()) / "recognica"
        self.env = {"COMMS_RECOGNICA_PATH": str(self.root)}

    def test_the_shelves_are_the_point(self):
        cards = [recognica_cards.new("ada", {"email": "ada@example.com"})]
        cards, made = recognica_roles.make_owner(cards, handles=[("email", "me@example.com")])
        cards, agent = recognica_roles.add_agent(cards, "peer bot", {"email": "bot@example.com"})
        self.assertEqual(made["shelf"], "humans/owner")
        self.assertEqual(agent["shelf"], "agents")
        self.assertEqual(recognica_cards.shelf(cards[0]), "humans/people")
        recognica_cards.save(cards, self.env)
        files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*.json"))
        self.assertEqual(files, ["agents/peer-bot.json", "humans/owner/owner.json", "humans/people/ada.json"])
        loaded = recognica_cards.load(self.env)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(recognica_roles.role_of(loaded, "email", "me@example.com")["role"], "owner")
        self.assertEqual(recognica_roles.role_of(loaded, "email", "ada@example.com")["role"], "contact")
        self.assertEqual(recognica_roles.role_of(loaded, "email", "bot@example.com")["role"], "agent")
        self.assertEqual(recognica_roles.role_of(loaded, "email", "who@example.com")["role"], "unknown")
        tree = recognica_cards.tree(loaded)
        self.assertEqual(tree["counts"], {"owner": 1, "people": 1, "agents": 1})

    def test_a_new_card_is_never_the_owner(self):
        card = recognica_cards.new("ada", {"email": "ada@example.com"})
        self.assertEqual(card["role"], "contact")
        self.assertIsNone(recognica_roles.owner([card]))
        self.assertFalse(recognica_roles.summary([card], env={})["knows_owner"])

    def test_the_owner_can_be_seeded_from_the_environment_without_being_guessed(self):
        cards = [recognica_cards.new("ada", {"email": "ada@example.com"})]
        cards, made = recognica_roles.make_owner(cards, env={"RECOGNICA_OWNER_EMAIL": "me@example.com"})
        self.assertTrue(made["ok"])
        self.assertEqual(recognica_roles.role_of(cards, "email", "me@example.com")["role"], "owner")
        # a second call updates the same card instead of adding a second owner
        cards, again = recognica_roles.make_owner(cards, handles=[("phone", "+15550001111")])
        self.assertEqual(len([c for c in cards if c["role"] == "owner"]), 1)
        self.assertTrue(again["ok"])
        nothing = recognica_roles.make_owner(cards, env={})[1]
        self.assertFalse(nothing["ok"])
        self.assertIn("RECOGNICA_OWNER", nothing["why"])

    def test_the_old_single_file_is_still_readable_after_the_move(self):
        self.root.mkdir(parents=True)
        (self.root / "cards.json").write_text(json.dumps([recognica_cards.new("ada")]))
        self.assertEqual([c["id"] for c in recognica_cards.load(self.env)], ["ada"])
        self.assertEqual([c["id"] for c in cardbook.load(self.env)], ["ada"])

    def test_saving_drops_a_card_that_moved_shelves(self):
        cards = [recognica_cards.new("ada", {"email": "ada@example.com"})]
        recognica_cards.save(cards, self.env)
        self.assertTrue((self.root / "humans/people/ada.json").is_file())
        cards, _ = recognica_roles.make_owner(cards + [], handles=[("email", "me@example.com")])
        cards[0]["role"] = "owner"
        recognica_cards.save(cards, self.env)
        self.assertFalse((self.root / "humans/people/ada.json").exists())
        self.assertTrue((self.root / "humans/owner/ada.json").is_file())


class TestTheOneCommand(unittest.TestCase):
    """this branch ships one command, and it points at the other half instead of copying it."""

    def test_setup_covers_every_lane(self):
        self.assertEqual(set(comms_cli.setup_payload()["lanes"]), set(registry.lanes()))

    def test_setup_points_telephony_at_its_own_command(self):
        self.assertIn("heyphony --setup", comms_cli.setup_payload()["telephony"])

    def test_the_shim_is_a_shim(self):
        shim = ROOT / "bin" / "comms"
        self.assertTrue(shim.is_file())
        self.assertTrue(os.access(shim, os.X_OK), "bin/comms has to be executable")
        self.assertIn("python3 -m comms.cli", shim.read_text())

    def test_the_shim_keeps_the_path_it_was_given(self):
        shim = (ROOT / "bin" / "comms").read_text()
        self.assertIn("${PYTHONPATH:+:$PYTHONPATH}", shim,
                      "the shim must not drop the path the number was found on")

    def test_status_closes_every_lane_when_the_environment_is_empty(self):
        import unittest.mock as mock
        with mock.patch.dict(os.environ, {}, clear=True):
            states = registry.states()
        self.assertTrue(states, "the registry found no lanes at all")
        for name, row in states.items():
            self.assertEqual(row["state"], "closed", f"{name} opened itself with no secret set")




class TestTheCatcherKnowsEveryLanePath(unittest.TestCase):
    """a route naming a folder that is not a lane is a typo nobody finds until a webhook fires."""

    def test_every_route_names_a_lane_that_exists(self):
        lanes = set(registry.folders())
        for route, name in catcher.ROUTES.items():
            self.assertIn(name, lanes, f"/{route} points at {name}, which is not a folder")

    def test_the_long_lived_lanes_have_no_route(self):
        for name in ("discord", "signal", "meetings", "streaming"):
            self.assertNotIn(name, catcher.ROUTES.values(),
                             f"{name} is not a webhook, so it must not have a route")

    def test_texts_are_not_caught_here(self):
        self.assertNotIn("sms", catcher.ROUTES, "texts belong to the number, which catches its own events")




class TestTheCatcherStoresWhatItVerifies(unittest.TestCase):
    """the point of the port: a signed event becomes one envelope in the store, and an unsigned one
    becomes a 401 with nothing kept. the number is stubbed, because its own tests are on main."""

    def serve(self, env):
        import threading
        import unittest.mock as mock
        from http.server import HTTPServer

        stored = []

        class Inbox:
            def append(self, entry, path=None):
                stored.append(entry)
                return True, "stored"

        stub = type("Number", (), {"inbox": staticmethod(lambda: Inbox())})
        patcher = mock.patch.object(catcher, "number", stub)
        patcher.start()
        self.addCleanup(patcher.stop)
        httpd = HTTPServer(("127.0.0.1", 0), catcher.make_handler(path=None, env=env))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return f"http://127.0.0.1:{httpd.server_address[1]}", stored

    def post(self, url, body, headers=None):
        request = urllib.request.Request(url, data=body.encode(), method="POST", headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=5) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def signed(self, secret, raw):
        """the v0 header pair slack and spectrum share, computed the way the carrier does it."""
        import hashlib
        import hmac
        ts = str(int(time.time()))
        signature = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:{raw}".encode(), hashlib.sha256).hexdigest()
        return {"x-slack-request-timestamp": ts, "x-slack-signature": signature,
                "content-type": "application/json"}

    def test_a_signed_event_is_stored_as_one_envelope(self):
        base, stored = self.serve({"SLACK_SIGNING_SECRET": "s3"})
        raw = json.dumps({"event": {"user": "U1", "text": "are you there"}})
        status, body = self.post(f"{base}/slack", raw, self.signed("s3", raw))
        self.assertEqual(status, 200, body)
        self.assertTrue(body["stored"])
        self.assertEqual(len(stored), 1, "one event is one message, not a row per field")
        entry = stored[0]
        self.assertEqual(entry["channel"], "slack")
        self.assertEqual(entry["sender"], "U1")
        self.assertEqual(entry["body"], "are you there")
        self.assertEqual(set(entry), set(envelope.KEYS), "the envelope grew or lost a key")

    def test_an_unsigned_event_is_a_401_and_is_not_kept(self):
        base, stored = self.serve({"SLACK_SIGNING_SECRET": "s3"})
        raw = json.dumps({"event": {"user": "U1", "text": "let me in"}})
        status, body = self.post(f"{base}/slack", raw, {"content-type": "application/json"})
        self.assertEqual(status, 401, body)
        self.assertEqual(stored, [], "an unverified payload reached the store")

    def test_a_wrong_signature_is_a_401_even_with_the_header_present(self):
        base, stored = self.serve({"SLACK_SIGNING_SECRET": "s3"})
        raw = json.dumps({"event": {"user": "U1", "text": "forged"}})
        status, _ = self.post(f"{base}/slack", raw, self.signed("not-the-secret", raw))
        self.assertEqual(status, 401)
        self.assertEqual(stored, [])

    def test_a_route_that_is_not_a_lane_is_a_404(self):
        base, stored = self.serve({"SLACK_SIGNING_SECRET": "s3"})
        status, body = self.post(f"{base}/myspace", "{}")
        self.assertEqual(status, 404, body)
        self.assertEqual(stored, [])

    def test_the_catcher_answers_which_lanes_it_knows(self):
        base, _ = self.serve({})
        with urllib.request.urlopen(f"{base}/", timeout=5) as answer:
            payload = json.loads(answer.read())
        self.assertIn("lanes", payload)
        self.assertEqual(set(payload["lanes"]), set(registry.folders()))


class TestTheNumberIsReachedByName(unittest.TestCase):
    """the one import this branch makes into the other half: it has to name the inbox module, not
    the folder that holds it, because an empty __init__ is not an inbox."""

    @unittest.skipUnless(HAVE_NUMBER, "the number is not on the path, so there is nothing to resolve")
    def test_the_resolution_lands_on_something_that_can_store_and_read(self):
        from comms import number
        module = number.inbox()
        self.assertTrue(hasattr(module, "append"), "the inbox module stores nothing")
        self.assertTrue(hasattr(module, "read"), "the inbox module reads nothing")
        self.assertNotEqual(getattr(module, "__name__", "").split(".")[-1], "manage",
                            "this resolved to the package folder rather than the inbox module")


class TestTheReadmesCannotDrift(unittest.TestCase):
    """prose that names carriers has to keep naming the ones that exist, and no others."""

    def readme(self):
        return (ROOT / "readme.md").read_text()

    def test_every_lane_in_the_tree_is_named_in_the_root_readme(self):
        text = self.readme().lower()
        for folder in registry.folders():
            self.assertIn(folder, text, f"{folder} is a lane but the readme does not mention it")

    def test_the_stack_is_described_as_a_stack(self):
        text = self.readme()
        for needle in ("omnichannel", "stack", "one memory", "turnkey", "rcs", "zoom",
                       "google meet", "teams", "screen"):
            self.assertIn(needle, text.lower(), f"the readme stopped claiming {needle!r}")
        self.assertNotIn("—", text, "no em dashes")

    def test_the_card_is_explained_where_a_human_will_look_for_it(self):
        text = self.readme().lower()
        self.assertIn("the card, so nobody pastes a chat again", text)
        self.assertIn("an unknown sender is stored, not stitched", text)

    def test_the_branch_readme_points_at_the_shelved_book(self):
        text = self.readme()
        self.assertIn("comms/recognica/readme.md", text)
        self.assertNotIn("comms/cards.py", text)
        for shelf in ("humans/owner", "humans/people", "agents/"):
            self.assertIn(shelf, text)
        self.assertTrue((ROOT / "comms" / "recognica" / "readme.md").is_file())
        self.assertTrue((ROOT / "comms" / "recognica" / "humans" / "owner" / "readme.md").is_file())

    def test_every_lane_readme_stays_a_page_rather_than_a_stub(self):
        for folder in registry.folders():
            page = ROOT / folder / "readme.md"
            self.assertTrue(page.is_file(), f"{folder} has no readme")
            text = page.read_text()
            self.assertGreater(len(text.split()), 60, f"{folder}/readme.md shrank to a stub")
            self.assertNotIn("—", text, f"{folder}/readme.md picked up an em dash")

    def test_the_lane_dicts_carry_the_same_facts(self):
        for folder in registry.folders():
            lane_dict = lane(folder).LANE
            for fact in ("name", "carrier", "intake", "relay", "gate", "state"):
                self.assertIn(fact, lane_dict, f"{folder}_lane.py is missing {fact!r}")
            self.assertIn(lane_dict["state"], ("verified", "designed", "closed", "refused"),
                          f"{folder} invented a state")

    def test_no_lane_claims_a_message_it_never_received(self):
        for folder in registry.folders():
            self.assertNotEqual(lane(folder).LANE["state"], "verified",
                                f"{folder} claims verified without an arrived message")





if __name__ == "__main__":
    unittest.main(verbosity=2)
