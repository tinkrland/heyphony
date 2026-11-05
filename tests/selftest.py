"""mobile selftests: stdlib only. run: python3 tests/selftest.py

three things are worth failing on here. the verbs drifting from the backends that actually offer
them, a line route that puts a long-lived sip password somewhere it will be thrown away, and a page
claiming a phone has been driven when nothing has been.
"""
import json
import os
import pathlib
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mobile  # noqa: E402

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
        self.assertEqual(payload["line"]["recommended"], "host-holds-the-line")
        self.assertEqual(payload["verified"], [])

    def test_routes_reports_where_the_secret_lives(self):
        done = subprocess.run([str(ROOT / "bin" / "mobile"), "routes"],
                              capture_output=True, text=True, timeout=60)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["recommended"]["route"], "host-holds-the-line")
        self.assertFalse(payload["routes"]["host-holds-the-line"]["phone_keeps_it"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
