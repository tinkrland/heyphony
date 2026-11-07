"""mobile selftests: stdlib only. run: python3 tests/selftest.py

three things are worth failing on here. the verbs drifting from the backends that actually offer
them, a line route that puts a long-lived sip password somewhere it will be thrown away, and a page
claiming a phone has been driven when nothing has been.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import client  # noqa: E402
import mobile  # noqa: E402
import ring as ring_rail  # noqa: E402

DUMP = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy rotation="0">
  <node text="" content-desc="Back" bounds="[0,0][72,72]"/>
  <node text="Allow" content-desc="" bounds="[100,200][300,280]"/>
  <node text="Sign in with phone" content-desc="" bounds="[40,400][400,480]"/>
  <node text="" content-desc="" bounds="[0,900][10,910]"/>
</hierarchy>"""


class TestTheVerbsAreFour(unittest.TestCase):
    def test_the_set_is_the_one_the_harness_documents(self):
        self.assertEqual(mobile.VERBS, ("open_app", "tap_text", "type_text", "screen"))

    def test_every_backend_offers_a_subset_of_the_four(self):
        for name, spec in mobile.BACKENDS.items():
            self.assertTrue(set(spec["verbs"]) <= set(mobile.VERBS), f"{name} invents a verb")
            for key in ("verbs", "covers", "why", "holds", "state"):
                self.assertIn(key, spec, f"{name} is missing {key}")

    def test_android_covers_all_four_and_ios_does_not_pretend(self):
        self.assertEqual(mobile.BACKENDS["android-adb"]["verbs"], list(mobile.VERBS))
        self.assertEqual(mobile.BACKENDS["ios-mirroring"]["verbs"], ["screen"])
        self.assertEqual(mobile.BACKENDS["ios-guest"]["verbs"], [])

    def test_no_backend_claims_to_be_verified(self):
        for name, spec in mobile.BACKENDS.items():
            self.assertNotEqual(spec["state"], "verified", f"{name} claims a phone was driven")


class TestTheRefusalsCarryAReason(unittest.TestCase):
    def test_ios_refuses_the_three_verbs_it_does_not_have(self):
        for verb in ("open_app", "tap_text", "type_text"):
            got = mobile.plan(verb, backend="ios-mirroring", pkg="x", xml_text=DUMP, text="x")
            self.assertTrue(got.get("refused"), f"ios-mirroring should refuse {verb}")
            self.assertIn("ios-mirroring offers", got["why"])
        self.assertIn("vision reads", mobile.plan("tap_text", backend="ios-mirroring")["reason"])

    def test_a_simulator_gets_alternatives_rather_than_a_verb(self):
        got = mobile.plan("screen", backend="ios-guest")
        self.assertTrue(got["refused"])
        self.assertEqual(got["alternatives"], ["android-adb"])

    def test_an_unknown_backend_or_verb_says_what_the_set_is(self):
        self.assertTrue(mobile.plan("screen", backend="nokia-3310")["refused"])
        with self.assertRaises(ValueError) as caught:
            mobile.plan("scroll", backend="android-adb")
        self.assertIn("unknown verb", str(caught.exception))

    def test_the_refusal_list_names_the_things_it_will_not_do(self):
        for key in ("borrowed-identity", "ocr-pretending-to-press", "silent-tap",
                    "secret-in-burn", "attestation-fiction", "camera-pretending"):
            self.assertIn(key, mobile.REFUSED, f"{key} fell out of the refusal list")


class TestATapComesOutOfADump(unittest.TestCase):
    def test_a_tap_without_a_dump_asks_for_one(self):
        got = mobile.plan("tap_text", label="Allow")
        self.assertEqual(got["needs"], ["dump_tree", "read_tree"])
        self.assertIn("guess with a screenshot", got["why"])

    def test_the_label_becomes_the_centre_of_the_node(self):
        got = mobile.plan("tap_text", label="Allow", xml_text=DUMP)
        self.assertEqual(got, ["adb", "shell", "input", "tap", "200", "240"])

    def test_a_content_description_is_a_label_too(self):
        node = mobile.find_node(DUMP, "back")
        self.assertEqual((node["x"], node["y"]), (36, 36))

    def test_a_missing_label_lists_what_the_tree_offers(self):
        with self.assertRaises(LookupError) as caught:
            mobile.find_node(DUMP, "Continue")
        self.assertIn("Sign in with phone", str(caught.exception))

    def test_something_that_is_not_a_dump_is_not_parsed_anyway(self):
        with self.assertRaises(ValueError):
            mobile.find_node("<not-a-dump", "Allow")

    def test_typing_escapes_what_the_adb_shell_eats(self):
        self.assertEqual(mobile.plan("type_text", text="hello world"),
                         ["adb", "shell", "input", "text", "hello%sworld"])
        self.assertEqual(mobile.escape_text("100%"), "100\\%")

    def test_opening_an_app_needs_a_package(self):
        self.assertEqual(mobile.plan("open_app")["needs"], ["pkg"])
        self.assertIn("monkey", " ".join(mobile.plan("open_app", pkg="com.android.settings")))


class TestTheLineRoutes(unittest.TestCase):
    def test_a_did_is_one_registration_on_every_route(self):
        for name, route in mobile.LINE_ROUTES.items():
            self.assertEqual(route["registrations"], 1, f"{name} invents a second line")
            for key in ("what", "secret_on", "phone_keeps_it", "survives_phone_burn",
                        "secrets_to_rotate", "needs", "honest", "state"):
                self.assertIn(key, route, f"{name} is missing {key}")

    def test_the_recommended_route_never_puts_the_secret_on_the_phone(self):
        picked = mobile.recommend()
        route = mobile.LINE_ROUTES[picked["route"]]
        self.assertFalse(route["phone_keeps_it"])
        self.assertTrue(route["survives_phone_burn"])
        self.assertIn("never reaches the phone", picked["because"])

    def test_the_routes_that_keep_the_secret_off_the_phone_are_named(self):
        self.assertEqual(sorted(mobile.routes_that_keep_the_secret_off_the_phone()),
                         ["host-holds-the-line", "phone-holds-the-account"])

    def test_putting_the_did_on_the_phone_names_the_race_it_starts(self):
        route = mobile.LINE_ROUTES["app-registers-the-did"]
        self.assertTrue(route["phone_keeps_it"])
        self.assertFalse(route["survives_phone_burn"])
        self.assertIn("host stops registering", " ".join(route["needs"]))

    def test_a_route_that_is_not_there_says_what_the_set_is(self):
        with self.assertRaises(ValueError) as caught:
            mobile.route("carrier-magic")
        self.assertIn("unknown route", str(caught.exception))

    def test_no_route_is_sold_as_verified(self):
        self.assertEqual([k for k, v in mobile.LINE_ROUTES.items() if v["state"] == "verified"], [])


class TestTheChecksTable(unittest.TestCase):
    def test_every_check_answers_the_same_five_questions(self):
        for name, row in mobile.CHECKS.items():
            for key in ("sees", "a_did_answers", "a_phone_we_hold_answers",
                        "a_guest_answers", "why"):
                self.assertIn(key, row, f"{name} is missing {key}")

    def test_the_did_answers_the_code_and_nothing_about_hardware(self):
        self.assertTrue(mobile.check("sms-code")["a_did_answers"].startswith("yes"))
        self.assertTrue(mobile.check("device-attestation")["a_did_answers"].startswith("no"))

    def test_the_three_checks_a_guest_fails_are_the_reason_to_hold_a_phone(self):
        self.assertEqual(sorted(mobile.checks_a_guest_fails()),
                         ["camera", "device-attestation", "sensor-tells"])

    def test_an_unknown_check_lists_the_set(self):
        with self.assertRaises(ValueError):
            mobile.check("vibes")


class TestThePageMatchesTheData(unittest.TestCase):
    def setUp(self):
        self.page = (ROOT / "readme.md").read_text()

    def test_every_route_is_on_the_page(self):
        for name in mobile.LINE_ROUTES:
            self.assertIn(f"`{name}`", self.page, f"the page does not name {name}")

    def test_every_backend_verb_and_check_is_on_the_page(self):
        for name in mobile.BACKENDS:
            self.assertIn(f"`{name}`", self.page, f"the page does not name {name}")
        for verb in mobile.VERBS:
            self.assertIn(verb, self.page, f"the page does not name {verb}")
        for name in mobile.CHECKS:
            self.assertIn(name, self.page, f"the page does not name {name}")

    def test_the_refusals_are_written_out_rather_than_listed_as_keys(self):
        for phrase in ("a borrowed identity", "attestation fiction", "a secret in the burn lane",
                       "ocr pretending to press", "a silent tap", "camera pretending"):
            self.assertIn(phrase, self.page, f"the page lost {phrase!r}")

    def test_the_page_credits_the_project_it_borrowed_from(self):
        self.assertIn("phone-harness", self.page)
        self.assertIn("github.com/phone-harness/phone-harness", self.page)
        self.assertIn("mit", self.page.lower())
        self.assertIn("local mode", self.page)

    def test_the_page_admits_nothing_has_been_driven(self):
        for needle in ("nothing on this branch has driven a phone yet",
                       "the first honest proof"):
            self.assertIn(needle, self.page)

    def test_no_page_picked_up_an_em_dash(self):
        for page in (ROOT / "readme.md",):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")


class TestTheOneCommand(unittest.TestCase):
    def test_the_shim_extends_the_path_and_runs_the_cli(self):
        shim = (ROOT / "bin" / "mobile").read_text()
        self.assertIn("python3 -m mobile_cli", shim)
        self.assertIn("${PYTHONPATH:+:$PYTHONPATH}", shim)
        self.assertTrue(os.access(ROOT / "bin" / "mobile", os.X_OK))

    def test_setup_answers_with_the_branch_in_one_object(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "--setup"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["branch"], "mobile")
        self.assertEqual(payload["linchpin"]["route"], "host-holds-the-line")
        self.assertEqual(payload["verified"], [])
        self.assertEqual(payload["state"], "designed")

    def test_prove_answers_with_the_ladder_in_order(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "prove"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["count"], len(payload["steps"]))
        self.assertEqual(payload["steps"][0]["argv"], ["adb", "devices"],
                         "the wire is the first thing that can fail, so it is the first step")

    def test_routes_reports_where_the_secret_lives(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "routes"],
                              capture_output=True, text=True, timeout=60)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["recommended"]["route"], "host-holds-the-line")
        self.assertFalse(payload["routes"]["host-holds-the-line"]["phone_keeps_it"])


class TestTheLanePagePointsAtTheSetup(unittest.TestCase):
    """a branch whose page does not say how it is driven is a note, not a branch."""

    def test_the_page_names_the_setup_commands_and_the_runbook(self):
        text = (ROOT / "readme.md").read_text()
        for needle in ("bin/mobile --setup", "bin/mobile prove", "[docs/setup.md](docs/setup.md)"):
            self.assertIn(needle, text, f"the page stopped naming {needle!r}")
        self.assertTrue((ROOT / "docs" / "setup.md").is_file())

    def test_the_page_keeps_the_honest_order_of_the_ladder(self):
        text = (ROOT / "readme.md").read_text()
        opened = text.index("one app opened and one screen read")
        tapped = text.index("a tap that came out of a real dump")
        iphone = text.index("the same three on an iphone")
        hardware = text.index("a hardware check that a guest would fail")
        self.assertLess(opened, tapped)
        self.assertLess(tapped, iphone)
        self.assertLess(iphone, hardware)


class TestTheSetupPlan(unittest.TestCase):
    """the plan is what an agent reads before touching a phone, so its shape is the contract."""

    def setUp(self):
        import mobile
        self.mobile = mobile
        self.plan = mobile.setup_plan()

    def test_the_plan_carries_the_keys_the_rest_of_the_repo_answers_with(self):
        for key in ("branch", "from_owner", "env", "areas", "prove", "rules", "verified", "linchpin"):
            self.assertIn(key, self.plan, f"the plan lost {key}")
        self.assertEqual(self.plan["branch"], "mobile")

    def test_the_human_acts_name_the_act_and_the_reason(self):
        self.assertTrue(self.plan["from_owner"], "a phone needs a person somewhere")
        for row in self.plan["from_owner"]:
            self.assertTrue(row["act"] and row["why"], f"an act lost half of itself: {row}")
        acts = " ".join(r["act"] for r in self.plan["from_owner"]).lower()
        for needle in ("debugging prompt", "unlock", "sign into", "camera"):
            self.assertIn(needle, acts, f"the acts stopped naming {needle!r}")

    def test_no_secret_enters_this_branch(self):
        env = self.plan["env"]
        self.assertEqual(env["required"], [], "the routes exist so that nothing here needs a credential")
        self.assertIn("no secret", env["note"])

    def test_every_area_points_at_a_subcommand_that_exists(self):
        known = {"status", "prove", "wake", "answer", "client", "ring", "routes", "verbs", "checks", "plan"}
        for name, row in self.plan["areas"].items():
            self.assertTrue(row["asks"] and row["answers"], f"the area {name!r} is half written")
            command = row["command"].split()
            self.assertEqual(command[0], "bin/mobile")
            self.assertIn(command[1], known, f"{name!r} points at {command[1]!r}, which the cli does not have")

    def test_the_rules_are_the_refusals_and_nothing_is_verified(self):
        self.assertEqual(sorted(self.plan["rules"]), sorted(self.mobile.REFUSED))
        self.assertEqual(self.plan["verified"], [])
        self.assertEqual(self.plan["state"], "designed")
        self.assertEqual(self.plan["linchpin"]["route"], "host-holds-the-line")


class TestTheProveLadder(unittest.TestCase):
    """a ladder whose rungs are out of order is advice, not a ladder."""

    def setUp(self):
        import mobile
        self.mobile = mobile
        self.steps = mobile.setup_plan()["prove"]

    def test_every_step_says_what_it_proves_and_what_to_watch(self):
        for step in self.steps:
            for key in ("step", "backend", "proves", "watch_out", "state"):
                self.assertIn(key, step, f"a step lost {key}: {step}")
            self.assertIn(step["state"], ("designed", "verified"))
            self.assertEqual(step["state"], "designed", "nothing has driven a phone, so nothing is verified")

    def test_a_step_names_an_argv_or_the_two_calls_that_produce_one(self):
        for step in self.steps:
            has_argv = "argv" in step
            has_needs = "needs" in step
            self.assertTrue(has_argv != has_needs, f"{step['step']} has both or neither")

    def test_the_dump_comes_before_the_tap(self):
        names = [s["step"] for s in self.steps]
        dump = next(i for i, n in enumerate(names) if "dump" in n)
        tap = next(i for i, n in enumerate(names) if "tap" in n)
        self.assertLess(dump, tap, "a tap with no dump before it is the thing this branch refuses")

    def test_the_wire_is_first_and_the_iphone_is_last(self):
        self.assertEqual(self.steps[0]["argv"], ["adb", "devices"])
        self.assertEqual(self.steps[-1]["backend"], "ios-mirroring")

    def test_the_argv_comes_from_plan_rather_than_being_retyped(self):
        opened = [s for s in self.steps if s["step"] == "open a stock app"][0]
        self.assertEqual(opened["argv"], self.mobile.plan("open_app", pkg="com.android.dialer"))


class TestTheRunbook(unittest.TestCase):
    """docs/setup.md is what a person follows, so it has to agree with the data it summarises."""

    def setUp(self):
        self.page = (ROOT / "docs" / "setup.md")
        self.text = self.page.read_text()

    def test_the_page_exists_and_carries_no_em_dash(self):
        self.assertTrue(self.page.is_file())
        self.assertNotIn("\u2014", self.text)

    def test_the_page_names_the_command_the_areas_and_the_iphone_limit(self):
        for needle in ("bin/mobile --setup", "bin/mobile prove", "bin/mobile routes", "bin/mobile checks",
                       "unauthorized", "only a frame"):
            self.assertIn(needle, self.text, f"the runbook lost {needle!r}")

    def test_the_page_keeps_the_ladder_in_the_order_the_data_has(self):
        import mobile
        rows = [s["step"] for s in mobile.setup_plan()["prove"]]
        headings = [line.strip("| ").split(" | ")[0] for line in self.text.splitlines() if line.startswith("| ")]
        for step in rows:
            self.assertIn(step, headings, f"the table dropped {step!r}")

    def test_the_page_says_the_word_verified_is_still_unused(self):
        self.assertIn("nothing on this branch is `verified` yet", self.text)


class TestTheWakeQuestion(unittest.TestCase):
    """registered is not ringing: the branch overstated this and the table is the correction."""

    def test_every_wake_row_carries_the_answer_and_the_lever(self):
        self.assertEqual(set(mobile.WAKE), {"android-app", "ios-app", "pstn-handset"})
        for name, row in mobile.WAKE.items():
            for key in ("what", "invite_while_idle", "lights_the_screen", "lever_we_hold", "honest", "state"):
                self.assertIn(key, row, f"{name} is missing {key}")
                self.assertTrue(str(row[key]).strip(), f"{name}.{key} is empty")
            self.assertEqual(row["state"], "designed", f"{name} claims more than a shape")

    def test_only_the_routes_whose_phone_answers_carry_a_wake_row(self):
        self.assertEqual(mobile.routes_that_can_ring(),
                         ["app-registers-the-did", "provision-onto-phone"])
        for name, row in mobile.LINE_ROUTES.items():
            self.assertIn("wake", row, f"{name} does not say whether it rings")
            for woken in (row["wake"] or ()):
                self.assertIn(woken, mobile.WAKE, f"{name} points at a wake row that is not there")
        self.assertIsNone(mobile.LINE_ROUTES["host-holds-the-line"]["wake"])

    def test_the_three_answers_are_the_ones_that_matter(self):
        self.assertIn("doze", mobile.WAKE["android-app"]["invite_while_idle"])
        self.assertIn("full screen intent", mobile.WAKE["android-app"]["lights_the_screen"])
        self.assertIn("callkit", mobile.WAKE["ios-app"]["lights_the_screen"])
        self.assertIn("pushkit", mobile.WAKE["ios-app"]["lights_the_screen"])
        self.assertIn("cannot wake a locked iphone", mobile.WAKE["ios-app"]["lights_the_screen"])
        self.assertIn("person picks up", mobile.WAKE["pstn-handset"]["honest"])

    def test_the_overstatement_is_gone(self):
        what = mobile.LINE_ROUTES["app-registers-the-did"]["what"]
        self.assertIn("while the app is awake", what)
        self.assertNotIn("so the phone rings and talks", what)

    def test_the_command_answers_it_and_the_pages_agree(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "wake"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual([r["name"] for r in payload["rows"]], list(mobile.WAKE))
        self.assertIn("registered is not ringing", payload["short"])
        page = (ROOT / "readme.md").read_text()
        self.assertIn("registered is not ringing", page)
        for needle in ("an android app", "an iphone", "the carrier's own forward",
                       "doze parks the app's network", "suspends the app", "telephony stack answers"):
            self.assertIn(needle, page, f"the page lost the {needle!r} answer")
        self.assertIn("bin/mobile wake", (ROOT / "docs/setup.md").read_text())


class TestTheAnswerQuestion(unittest.TestCase):
    """waking the panel is cheap; being in the conversation is the part that decides the branch."""

    def test_every_answer_path_names_what_the_agent_gets(self):
        for name, row in mobile.ANSWER_PATH.items():
            for key in ("what", "agent_hears", "agent_speaks", "needs", "cost", "state"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertTrue(row["needs"], f"{name} needs nothing, which cannot be true")
            self.assertEqual(row["state"], "designed")
            self.assertNotEqual(row["state"], "verified", f"{name} is not proven")

    def test_only_two_shapes_give_the_agent_ears(self):
        self.assertEqual(mobile.answers_with_audio(), ["host-softphone", "our-own-app-in-a-room"])

    def test_the_phone_tap_row_admits_it_cannot_hear(self):
        row = mobile.ANSWER_PATH["phone-taps-answer"]
        self.assertTrue(row["agent_hears"].startswith("no"))
        self.assertTrue(row["agent_speaks"].startswith("no"))
        self.assertIn("adb", row["agent_hears"])

    def test_waking_is_answered_separately_from_answering(self):
        android = mobile.WAKE["android-app"]
        self.assertIn("deviceidle whitelist", android["wake_on_ring"])
        self.assertIn("full screen intent", android["wake_on_ring"])
        self.assertEqual(android["answer"], "phone-taps-answer")
        self.assertTrue(mobile.WAKE["ios-app"]["wake_on_ring"].startswith("no"))
        self.assertIsNone(mobile.WAKE["ios-app"]["answer"])
        self.assertIsNone(mobile.WAKE["pstn-handset"]["answer"])
        for name, row in mobile.WAKE.items():
            self.assertIn("wake_on_ring", row, f"{name} lost the ring question")
            self.assertIn("answer", row, f"{name} lost the answer pointer")

    def test_every_answer_pointer_names_a_real_path(self):
        for name, row in mobile.WAKE.items():
            if row["answer"]:
                self.assertIn(row["answer"], mobile.ANSWER_PATH, f"{name} points at {row['answer']}")

    def test_the_command_and_the_page_carry_it(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "answer"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(len(payload["paths"]), len(mobile.ANSWER_PATH))
        self.assertIn("a call the agent cannot hear", payload["short"])
        page = (ROOT / "readme.md").read_text()
        for needle in ("waking it is solvable on a phone we own", "the host softphone answers",
                       "the phone taps answer", "an app we ship that joins a room",
                       "waking it is the cheap part"):
            self.assertIn(needle, page, f"the page lost {needle!r}")


class TestTheClient(unittest.TestCase):
    """two shapes, five components, and nothing claimed: the build this branch could not do."""

    def test_the_shapes_carry_what_a_build_needs(self):
        self.assertEqual(sorted(client.SHAPES), ["host-bridge", "phone-app"])
        for name, row in client.SHAPES.items():
            for key in ("what", "components", "with_a_remote_brain", "wins", "costs", "proves_here",
                        "needs", "state"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertFalse(row["proves_here"], f"{name} claims it was proven here")
            self.assertEqual(row["state"], "designed")
            for component in row["components"]:
                self.assertIn(component, client.COMPONENTS, f"{name} names an unknown component")

    def test_the_host_bridge_is_first_and_the_reason_is_a_reason(self):
        first = client.first_shape()
        self.assertEqual(first["shape"], "host-bridge")
        self.assertIn("no phone", first["because"])
        self.assertIn("no signing identity", first["because"])

    def test_the_room_is_optional_until_the_brain_is_elsewhere(self):
        alone = [c["name"] for c in client.components_for("host-bridge")]
        remote = [c["name"] for c in client.components_for("host-bridge", remote_brain=True)]
        self.assertNotIn("room-leg", alone)
        self.assertIn("room-leg", remote)
        self.assertIn("consent", alone, "consent is not optional")

    def test_the_steps_run_in_the_order_the_call_needs(self):
        for name in client.SHAPES:
            steps = client.bridge_plan(name)["steps"]
            does = [step["does"] for step in steps]
            self.assertEqual(does[0], "sip-leg", f"{name} does not hold the line first")
            self.assertEqual(does[-1], "consent", f"{name} does not end by saying what it is")
            for step in steps:
                self.assertIn(step["does"], client.COMPONENTS)
                self.assertTrue(step["how"] and step["note"], f"{name} has a half-written step")

    def test_the_refusals_are_the_ones_that_make_a_client_safe(self):
        for needle in ("agent-hears-itself", "silent-recording", "unlabelled-bot", "cold-answer"):
            self.assertIn(needle, client.REFUSED)
        self.assertIn("echo", client.REFUSED["agent-hears-itself"])
        self.assertIn("what it is", client.REFUSED["unlabelled-bot"])

    def test_the_room_contract_forbids_the_echo_in_one_line(self):
        contract = client.room_contract()
        self.assertIn("never", contract["subscribe"])
        self.assertIn("off unless", contract["records"])
        self.assertEqual(contract["identity"], "the did, because the call is the identity that matters to the person on it")

    def test_the_first_proof_says_how_it_fails(self):
        for name in client.SHAPES:
            proof = client.first_proof(name)
            self.assertTrue(proof["call_it"] and proof["passes_when"] and proof["fails_loudly_when"])

    def test_the_command_answers_with_the_plan(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "client"], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["first"]["shape"], "host-bridge")
        self.assertEqual(payload["plan"]["proves_here"], False)
        self.assertIn("refusals", payload)

    def test_the_page_points_at_it_and_the_room_row_is_no_longer_a_wish(self):
        page = (ROOT / "readme.md").read_text()
        for needle in ("the host bridge goes first", "the phone app comes second",
                       "the agent never subscribes to the mouth it publishes",
                       "pulseaudio's sink keeps its own clock"):
            self.assertIn(needle, page, f"the page lost {needle!r}")
        self.assertIn("client.py", page)
        self.assertIn("client.py", mobile.ANSWER_PATH["our-own-app-in-a-room"]["cost"])


class TestTheRecordedProof(unittest.TestCase):
    """the run is a measurement, so its shape is pinned and its failures stay failures."""

    def test_the_host_is_named_because_a_measurement_without_one_is_a_rumour(self):
        for key in ("host", "at", "tools", "how"):
            self.assertTrue(client.PROOF_HOST[key], f"the proof host lost {key!r}")
        self.assertIn("no sound card", client.PROOF_HOST["host"])
        self.assertIn("bench/first_proof.py", client.PROOF_HOST["how"])

    def test_every_rung_says_what_happened_and_why(self):
        states = {"passed", "failed", "skipped"}
        for row in client.PROVEN:
            self.assertEqual(set(row), {"rung", "state", "because"})
            self.assertIn(row["state"], states)
            self.assertGreater(len(row["because"]), 40, f"{row['rung']} says nothing")

    def test_the_counts_match_what_the_harness_reported(self):
        run = client.attempt()
        self.assertEqual(run["counts"], {"passed": 4, "skipped": 2})
        self.assertEqual([r["rung"] for r in run["rows"]], [r["rung"] for r in client.PROVEN])

    def test_the_audio_flow_names_the_daemon_that_carried_it(self):
        """it passes, and the whole value is knowing why: pulseaudio self-clocks and pipewire does not."""
        flow = [r for r in client.PROVEN if r["rung"] == "flow"][0]
        self.assertEqual(flow["state"], "passed")
        for needle in ("pulseaudio", "module-null-sink", "pipewire", "device"):
            self.assertIn(needle, flow["because"], f"the flow result lost {needle!r}")

    def test_the_audio_backends_say_which_one_clocks_itself(self):
        self.assertEqual(client.backs_that_self_clock(), ["pulseaudio", "jack-dummy"])
        self.assertTrue(client.audio_backend("pulseaudio")["self_clocks"])
        self.assertFalse(client.audio_backend("pipewire")["self_clocks"])
        self.assertEqual(client.audio_backend("pulseaudio")["state"], "verified")
        self.assertEqual(client.audio_backend("pipewire")["state"], "designed")
        self.assertEqual(client.audio_backend("jack-dummy")["state"], "designed",
                         "jack is named and not run")

    def test_the_two_rungs_that_need_the_world_skip_with_a_reason(self):
        by_rung = {r["rung"]: r for r in client.PROVEN}
        self.assertEqual(by_rung["call"]["state"], "skipped")
        self.assertIn("did", by_rung["call"]["because"])
        self.assertEqual(by_rung["phone"]["state"], "skipped")
        self.assertIn("device", by_rung["phone"]["because"])

    def test_no_call_is_verified_by_a_proof_run(self):
        self.assertEqual(mobile.setup_plan()["verified"], [])
        for shape in client.SHAPES.values():
            self.assertFalse(shape["proves_here"], "a local harness cannot stand in for a phone call")

    def test_the_harness_carries_the_same_rungs(self):
        bench = (ROOT / "bench" / "first_proof.py").read_text()
        for row in client.PROVEN:
            self.assertIn(f"def rung_{row['rung']}(", bench, f"the harness lost the {row['rung']} rung")
        self.assertIn("TimeoutExpired", bench, "a blocked step has to be a result, not a hang")
        page = (ROOT / "readme.md").read_text()
        self.assertEqual(len(client.PROOF_HOST["hosts_tried"]), 4,
                         "every host the flow rung was tried on belongs in the record")
        for needle in ("pulseaudio's `module-null-sink` keeps its own clock", "which daemon owns the sink"):
            self.assertIn(needle, page, f"the page lost {needle!r}")
        self.assertIn("node.always-process", bench,
                      "the headless lesson belongs in the harness: a sink without a card has to be its own driver")

    def test_the_pages_say_what_the_attempt_got(self):
        page = (ROOT / "readme.md").read_text()
        for needle in ("the first proof, attempted once for real", "the nodes are real",
                       "the callee can be driven", "the audio flow passes",
                       "bench/first_proof.py"):
            self.assertIn(needle, page, f"the page lost {needle!r}")
        runbook = (ROOT / "docs" / "setup.md").read_text()
        self.assertIn("python3 bench/first_proof.py", runbook)

    def test_no_em_dash_in_the_client_or_its_pages(self):
        for path in (ROOT / "client.py", ROOT / "readme.md", ROOT / "docs" / "setup.md"):
            self.assertNotIn("\u2014", path.read_text(), f"{path.name} has an em dash")


class TestWhatOtherBranchesOwn(unittest.TestCase):
    """three of the five components are borrowed, so this folder should never grow a second dial stack."""

    def test_every_component_says_where_it_lives(self):
        for name, row in client.SOURCED_FROM.items():
            for key in ("branch", "path", "what", "state", "note"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertIn(row["state"], ("designed", "verified"))

    def test_the_borrowed_ones_do_not_include_consent(self):
        self.assertEqual(sorted(client.borrowed_components()),
                         ["agent-ear", "agent-mouth", "room-leg", "sip-leg"])
        self.assertEqual(client.sourced_from("consent")["branch"], "mobile")

    def test_the_gaps_nobody_filled_are_named(self):
        self.assertEqual(sorted(client.NOBODY_HAS),
                         ["a-device", "android-toolchain", "sip-to-room-bridge"])
        self.assertIn("shipped: false", client.NOBODY_HAS["sip-to-room-bridge"])

    def test_the_call_rung_offers_a_far_end_that_is_not_a_person(self):
        proof = client.first_proof("host-bridge")
        without = proof["without_a_handset"]
        self.assertIn("echo or test number", without[1])
        self.assertIn("ringing", without[2])
        self.assertIn("registered a did", proof["blocked_on"])

    def test_the_phone_shape_names_what_it_waits_on(self):
        self.assertIn("sdk and a device", client.SHAPES["phone-app"]["blocked_on"])
        self.assertIn("emulator", client.SHAPES["phone-app"]["blocked_on"])

    def test_the_command_answers_it(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "client", "--sourced"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(len(payload["components"]), 5)
        self.assertIn("assembly rather than a build", payload["short"])
        page = (ROOT / "readme.md").read_text()
        self.assertIn("what the other branches already own", page)
        self.assertIn("the sip leg is `callheavy`", page)


class TestTheRingRail(unittest.TestCase):
    """the invite reaches the host, the host answers, and the notification rides beside it."""

    def test_the_event_that_matters_is_the_one_that_can_still_be_answered(self):
        self.assertIn("CALL_INCOMING", ring_rail.RING_EVENTS)
        self.assertIn("still ringable", ring_rail.RING_EVENTS["CALL_INCOMING"]["matters"])
        for name, row in ring_rail.RING_EVENTS.items():
            for key in ("when", "what_the_agent_gets", "matters"):
                self.assertIn(key, row, f"{name} is missing {key}")

    def test_the_channels_say_who_actually_reaches_a_sleeping_vm(self):
        for name, row in ring_rail.NOTIFY.items():
            for key in ("what", "reaches_a_sleeping_vm", "latency", "needs", "cost", "verdict"):
                self.assertIn(key, row, f"{name} is missing {key}")
        self.assertTrue(ring_rail.NOTIFY["push"]["reaches_a_sleeping_vm"])
        self.assertFalse(ring_rail.NOTIFY["webhook"]["reaches_a_sleeping_vm"],
                         "a webhook to a sleeping receiver is not a channel")
        self.assertIn("minutes", ring_rail.NOTIFY["email"]["latency"])
        self.assertIn("second", ring_rail.NOTIFY["push"]["latency"])

    def test_the_policy_is_the_one_that_beats_the_race(self):
        self.assertTrue(ring_rail.PICKUP["answer-then-tell"]["beats_the_race"])
        self.assertFalse(ring_rail.PICKUP["tell-then-answer"]["beats_the_race"])
        self.assertEqual(ring_rail.PICKUP["answer-then-tell"]["state"], "recommended")
        self.assertEqual(ring_rail.ring_plan()["policy"], "answer-then-tell")

    def test_the_budget_is_shorter_than_the_callers_patience(self):
        low, high = ring_rail.RING_BUDGET["caller_patience_s"]
        self.assertLess(low, high)
        self.assertLess(ring_rail.RING_BUDGET["decide_by_s"], low)
        self.assertIn("voicemail", ring_rail.RING_BUDGET["past_it"])

    def test_the_refusals_refuse_the_tempting_version(self):
        for needle in ("answer-blind", "notify-as-the-plan", "wake-the-phone-to-answer"):
            self.assertIn(needle, ring_rail.REFUSED)
        self.assertIn("thirty seconds", ring_rail.REFUSED["notify-as-the-plan"])

    def test_a_command_is_a_netstring_with_a_string_params(self):
        wire = ring_rail.command("answer")
        self.assertTrue(wire.endswith(b","))
        payload = json.loads(wire[wire.index(b":") + 1:-1])
        self.assertEqual(payload["command"], "answer")
        self.assertIsInstance(payload["params"], str, "baresip's ctrl_tcp wants params as a string")

    def test_the_decoder_takes_netstrings_bare_json_and_a_split_read(self):
        one = ring_rail.netstring(json.dumps({"type": "CALL_INCOMING"}).encode())
        two = json.dumps({"type": "CALL_CLOSED"}).encode()
        messages, rest = ring_rail.decode(one + two)
        self.assertEqual([m["type"] for m in messages], ["CALL_INCOMING", "CALL_CLOSED"])
        self.assertEqual(rest, b"")
        half = one[:5]
        messages, rest = ring_rail.decode(half)
        self.assertEqual(messages, [])
        messages, rest = ring_rail.decode(rest + one[5:])
        self.assertEqual([m["type"] for m in messages], ["CALL_INCOMING"])

    def test_the_whole_chain_answers_and_notifies_on_one_socket(self):
        """the proof this rail can have without a registration: a fake baresip on a socket pair."""
        host, peer = socket.socketpair()
        notes = []
        rail = ring_rail.Ring(host, notify=notes.append)
        event = {"event": True, "class": "call", "type": "CALL_INCOMING", "id": "call-7",
                 "peeruri": "sip:caller@example.net"}
        peer.sendall(ring_rail.netstring(json.dumps(event).encode()))
        self.assertTrue(rail.pump(until=lambda m: m.get("type") == "CALL_INCOMING", timeout=5))
        self.assertEqual(len(notes), 1, "a ringing call produced no notification")
        self.assertEqual(notes[0]["peer"], "sip:caller@example.net")
        self.assertEqual(notes[0]["call_id"], "call-7")
        self.assertEqual(notes[0]["kind"], "ringing")
        peer.settimeout(5)
        answered, _ = ring_rail.decode(peer.recv(4096))
        self.assertEqual(answered[0]["command"], "answer", "answer-then-tell did not answer")
        host.close()
        peer.close()

    def test_tell_then_answer_does_not_answer_on_its_own(self):
        host, peer = socket.socketpair()
        notes = []
        rail = ring_rail.Ring(host, notify=notes.append, policy="tell-then-answer")
        peer.sendall(ring_rail.netstring(json.dumps({"class": "call", "type": "CALL_INCOMING",
                                                     "id": "call-8", "peeruri": "sip:x@y"}).encode()))
        rail.pump(until=lambda m: m.get("type") == "CALL_INCOMING", timeout=5)
        self.assertEqual(len(notes), 1)
        self.assertEqual(rail.sent, [], "the patient policy answered the phone anyway")
        rail.hangup()
        self.assertEqual(rail.sent, [ring_rail.command("hangup")])
        host.close()
        peer.close()

    def test_the_notification_is_a_line_a_tail_can_read(self):
        target = pathlib.Path(tempfile.mkdtemp()) / "rings.jsonl"
        message = ring_rail.notify_message({"type": "CALL_INCOMING", "id": "c1", "peeruri": "sip:a@b"})
        ring_rail.write_notification(message, str(target))
        ring_rail.write_notification(message, str(target))
        lines = target.read_text().strip().splitlines()
        self.assertEqual(len(lines), 2, "two calls should be two lines")
        self.assertEqual(json.loads(lines[0])["call_id"], "c1")

    def test_the_command_and_the_page_carry_it(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "ring"], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["plan"]["policy"], "answer-then-tell")
        self.assertEqual(len(payload["plan"]["steps"]), 7)
        self.assertIn("thirty seconds", payload["short"])
        page = (ROOT / "readme.md").read_text()
        self.assertIn("a call it can see", page)
        runbook = (ROOT / "docs" / "setup.md").read_text()
        self.assertIn("bin/mobile ring", runbook)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
