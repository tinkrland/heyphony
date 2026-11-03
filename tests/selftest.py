"""meetings selftests: stdlib only. run: python3 tests/selftest.py

the failures worth catching on this branch are prose drifting from `rails.py`, a token that verifies
when it should not, a plan that assumes a rail the environment never opened, a microphone story that
calls closed source free, and anything that quietly turns on a recording.
"""
import base64
import json
import os
import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "meetings"))

import rails  # noqa: E402
import audio  # noqa: E402
from meetings import cli as meetings_cli  # noqa: E402
from meetings import meetings_lane as lane  # noqa: E402

OPEN_ZOOM = {"ZOOM_SDK_KEY": "k", "ZOOM_SDK_SECRET": "s"}


class TestTheRailsAreData(unittest.TestCase):
    def test_every_rail_carries_the_facts_a_join_needs(self):
        for name, row in rails.RAILS.items():
            for key in ("name", "join", "signature", "audio", "screenshare", "gate", "signal",
                        "evidence", "state", "refused", "scope"):
                self.assertIn(key, row, f"{name} is missing {key}")
            self.assertEqual(row["name"], name)
            self.assertTrue(row["gate"], f"{name} has no gate")
            self.assertIn(row["state"], rails.STATES)

    def test_nothing_claims_a_joined_meeting(self):
        self.assertEqual(rails.by_state("verified"), [],
                         "no meeting has been joined, so `verified` is not available yet")
        self.assertEqual(sorted(rails.by_state("designed")), sorted(rails.RAILS),
                         "every rail is designed: the join path is read and implemented")

    def test_only_zoom_carries_a_signature(self):
        self.assertIsNotNone(rails.signature_of("zoom"))
        self.assertIsNone(rails.signature_of("googlemeet"))
        self.assertIsNone(rails.signature_of("teams"))

    def test_the_zoom_signature_is_the_one_the_docs_describe(self):
        signature = rails.signature_of("zoom")
        self.assertEqual(signature["alg"], "HS256")
        self.assertIn("sdkKey", signature["payload"])
        self.assertIn("mn", signature["payload"])
        self.assertIn("minus 30 seconds", signature["why_backdated"])
        self.assertIn("tokenExp", signature["payload"])


class TestTheLaneReadsTheRails(unittest.TestCase):
    """one table. a second copy of the three platforms is the drift this branch does not keep."""

    def test_the_platforms_are_the_rails(self):
        self.assertEqual(sorted(lane.PLATFORMS), sorted(rails.RAILS))
        for name, spec in lane.PLATFORMS.items():
            self.assertEqual(spec["gate"], tuple(rails.RAILS[name]["gate"]))
            self.assertEqual(spec["state"], rails.RAILS[name]["state"])
            self.assertEqual(spec["join"], rails.RAILS[name]["join"])

    def test_the_lane_gate_is_the_zoom_gate(self):
        self.assertEqual(set(lane.LANE["gate"]), set(rails.RAILS["zoom"]["gate"]))

    def test_the_lane_carries_evidence_rather_than_a_claim(self):
        self.assertEqual(lane.LANE["state"], "designed")
        for fact in ("carrier", "intake", "relay", "gate", "state", "evidence"):
            self.assertIn(fact, lane.LANE)
        self.assertIn("no real meeting has been joined", lane.LANE["evidence"])


class TestTheZoomToken(unittest.TestCase):
    def test_a_minted_token_verifies(self):
        token = lane.sign_zoom_join("81234567890", env=OPEN_ZOOM)["join_token"]
        self.assertTrue(lane.verify_zoom_token(token, env=OPEN_ZOOM))

    def test_two_joins_of_the_same_meeting_do_not_look_alike(self):
        first = lane.sign_zoom_join("81234567890", env=OPEN_ZOOM)["join_token"]
        second = lane.sign_zoom_join("81234567890", env=OPEN_ZOOM)["join_token"]
        self.assertNotEqual(first, second, "the random tail exists so two joins never match")

    def test_the_signature_covers_the_header_and_the_payload(self):
        token = lane.sign_zoom_join("99", env=OPEN_ZOOM)["join_token"]
        parts = base64.b64decode(token).decode().split(".")
        self.assertEqual(len(parts), 4, "signature, header, payload, tail")
        changed_payload = base64.b64encode(
            ".".join([parts[0], parts[1], parts[2] + "x", parts[3]]).encode()).decode()
        self.assertFalse(lane.verify_zoom_token(changed_payload, env=OPEN_ZOOM))

    def test_the_tail_is_a_nonce_and_carries_no_claim(self):
        token = lane.sign_zoom_join("99", env=OPEN_ZOOM)["join_token"]
        parts = base64.b64decode(token).decode().split(".")
        other_tail = base64.b64encode(
            ".".join([parts[0], parts[1], parts[2], "f" * 8]).encode()).decode()
        self.assertTrue(lane.verify_zoom_token(other_tail, env=OPEN_ZOOM),
                        "the tail is not covered, so changing it changes nothing")

    def test_a_forged_signature_is_rejected(self):
        token = lane.sign_zoom_join("99", env=OPEN_ZOOM)["join_token"]
        parts = base64.b64decode(token).decode().split(".")
        forged = base64.b64encode(
            ".".join(["A" * len(parts[0]), parts[1], parts[2], parts[3]]).encode()).decode()
        self.assertFalse(lane.verify_zoom_token(forged, env=OPEN_ZOOM))

    def test_another_secret_does_not_verify_our_token(self):
        token = lane.sign_zoom_join("99", env=OPEN_ZOOM)["join_token"]
        self.assertFalse(lane.verify_zoom_token(token, env={"ZOOM_SDK_SECRET": "other"}))

    def test_rubbish_is_not_a_token(self):
        for value in ("", "not-a-token", "a.b.c", "!!!!"):
            self.assertFalse(lane.verify_zoom_token(value, env=OPEN_ZOOM))

    def test_a_closed_lane_mints_nothing(self):
        with self.assertRaises(RuntimeError):
            lane.sign_zoom_join("99", env={})

    def test_the_issued_time_is_backdated_thirty_seconds(self):
        token = lane.sign_zoom_join("99", now=1_700_000_000, env=OPEN_ZOOM)
        self.assertEqual(token["iat"], 1_700_000_000 - 30)
        self.assertEqual(token["exp"], token["iat"] + 7200)
        payload = json.loads(base64.b64decode(base64.b64decode(token["join_token"]).decode()
                                             .split(".")[2]))
        self.assertEqual(payload["mn"], "99")
        self.assertEqual(payload["role"], 0)


class TestTheJoinPlan(unittest.TestCase):
    def test_an_open_zoom_lane_is_joinable_and_carries_the_token(self):
        plan = lane.join_plan("zoom", "81234567890", env=OPEN_ZOOM)
        self.assertTrue(plan["joinable"])
        self.assertEqual(plan["missing"], [])
        self.assertIn("token", plan)
        self.assertTrue(lane.verify_zoom_token(plan["token"]["join_token"], env=OPEN_ZOOM))

    def test_a_closed_lane_says_which_variables_are_missing(self):
        plan = lane.join_plan("zoom", "1", env={})
        self.assertFalse(plan["joinable"])
        self.assertEqual(sorted(plan["missing"]), ["ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"])
        self.assertNotIn("token", plan, "a closed lane must not mint a token")

    def test_the_browser_rooms_never_get_a_token(self):
        for platform in ("googlemeet", "teams"):
            plan = lane.join_plan(platform, "abc", env={"MEETING_BROWSER_PROFILE": "/p"})
            self.assertNotIn("token", plan, f"{platform} has no signature to mint")
            self.assertEqual(rails.signature_of(platform), None)

    def test_a_platform_that_is_not_modelled_names_the_ones_that_are(self):
        plan = lane.join_plan("myspace", "1", env=OPEN_ZOOM)
        self.assertFalse(plan["joinable"])
        self.assertFalse(plan["modelled"])
        self.assertEqual(sorted(plan["known"]), sorted(rails.RAILS))

    def test_the_plan_carries_both_rails_and_the_scope(self):
        plan = lane.join_plan("zoom", "1", env=OPEN_ZOOM)
        self.assertEqual(sorted(plan["rails"]), ["audio", "screenshare"])
        self.assertIn("renders and hands back", plan["scope"])
        self.assertIn("signal", plan)

    def test_no_plan_offers_a_recording(self):
        plan = lane.join_plan("zoom", "1", env=OPEN_ZOOM)
        self.assertNotIn("record", json.dumps(plan).lower().replace("recorded", ""))


class TestTheAudioRails(unittest.TestCase):
    def test_every_piece_on_the_audio_path_is_free_software(self):
        report = audio.audit()
        self.assertTrue(report["all_oss"])
        self.assertEqual(report["not_oss"], ["vb-cable"], "the closed one is named, not hidden")

    def test_obs_is_free_software_and_still_not_the_microphone(self):
        self.assertTrue(audio.is_oss("obs"))
        self.assertIn("obs", audio.audit()["not_needed_for_audio"])

    def test_a_browser_room_needs_no_device(self):
        mic = audio.browser_mic("agent-voice.wav")
        self.assertEqual(mic["mode"], "chromium-flags")
        self.assertIn("--use-fake-device-for-media-stream", mic["argv"])
        self.assertIn("--use-file-for-fake-audio-capture=agent-voice.wav", mic["argv"])
        self.assertIn("wav, not a stream", mic["caveat"])

    def test_a_native_client_gets_a_null_sink_on_linux(self):
        mic = audio.virtual_mic("linux")
        self.assertEqual(mic["mode"], "null-sink")
        self.assertEqual(mic["commands"][0][:3], ["pactl", "load-module", "module-null-sink"])
        self.assertIn("mit", mic["note"])

    def test_macos_and_windows_need_an_install_and_say_what_it_costs(self):
        mac = audio.virtual_mic("macos")
        windows = audio.virtual_mic("windows")
        self.assertEqual(mac["mode"], "install-required")
        self.assertIn("gpl-3.0", mac["device"])
        self.assertIn("NOT free software", windows["note"])

    def test_an_unknown_platform_gets_no_invented_plan(self):
        self.assertEqual(audio.virtual_mic("plan9")["mode"], "unknown")

    def test_the_room_decides_the_rail(self):
        browser_room = audio.meeting_mic("zoom")
        self.assertEqual(browser_room["mode"], "chromium-flags")
        native = audio.meeting_mic("zoom", client="linphone")
        self.assertEqual(native["mode"], "null-sink")
        livekit = audio.meeting_mic("livekit")
        self.assertEqual(livekit["mode"], "livekit")
        self.assertIn("fallback", livekit)

    def test_readiness_reports_what_is_set_rather_than_assuming(self):
        self.assertFalse(audio.readiness({})["livekit"])
        self.assertTrue(audio.readiness({"LIVEKIT_URL": "wss://x", "LIVEKIT_API_KEY": "k",
                                         "LIVEKIT_API_SECRET": "s"})["livekit"])
        self.assertTrue(audio.readiness({})["browser_room"],
                        "we launch the browser, so its flags are always available")


class TestTheOneCommand(unittest.TestCase):
    def test_the_setup_payload_covers_every_platform(self):
        self.assertEqual(set(meetings_cli.setup_payload({})["platforms"]), set(rails.RAILS))

    def test_setup_names_what_is_open_and_what_is_not(self):
        self.assertEqual(meetings_cli.setup_payload({})["open"], [])
        self.assertEqual(sorted(meetings_cli.setup_payload(OPEN_ZOOM)["open"]), ["zoom"])

    def test_status_lists_the_missing_gate_per_platform(self):
        status = meetings_cli.status_payload({})
        self.assertEqual(status["platforms"]["zoom"]["missing"], ["ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"])
        self.assertEqual(status["platforms"]["teams"]["state"], "designed")
        self.assertIn("audio", status)

    def test_the_shim_is_a_shim(self):
        shim = ROOT / "bin" / "meetings"
        self.assertTrue(shim.is_file())
        self.assertTrue(os.access(shim, os.X_OK), "bin/meetings has to be executable")
        text = shim.read_text()
        self.assertIn("python3 -m meetings.cli", text)
        self.assertIn("${PYTHONPATH:+:$PYTHONPATH}", text,
                      "the shim must extend the path rather than replace it")


class TestThePageMatchesTheData(unittest.TestCase):
    page = ROOT / "readme.md"

    def test_every_rail_is_on_the_page(self):
        text = self.page.read_text()
        for name, join, signature, audio_path, state in rails.table_rows():
            self.assertIn(f"`{name}`", text, f"the page does not list {name}")
            self.assertIn(audio_path, text, f"the page does not name {name}'s audio path")

    def test_the_page_admits_what_the_state_is(self):
        text = self.page.read_text()
        self.assertIn("state is `designed` on every row", text)
        self.assertIn("nothing on this branch joins a meeting yet", text)

    def test_the_page_names_the_rename(self):
        text = self.page.read_text()
        self.assertIn("used to be called `omnimeetings`", text)
        self.assertIn("# meetings", text)

    def test_the_three_human_acts_are_on_the_page(self):
        text = self.page.read_text()
        for needle in ("sends the invite", "stays in the loop on recording",
                       "decides what the agent is for"):
            self.assertIn(needle, text, f"the page lost {needle!r}")

    def test_the_refusals_are_named(self):
        text = self.page.read_text()
        for needle in ("no cold joins", "no recording by default", "no broadcast"):
            self.assertIn(needle, text, f"the page lost {needle!r}")

    def test_the_page_says_what_runs(self):
        text = self.page.read_text()
        for needle in ("bin/meetings", "meetings/meetings_lane.py", "audio.py"):
            self.assertIn(needle, text, f"the page does not say {needle} exists")


class TestTheLanePage(unittest.TestCase):
    page = ROOT / "meetings" / "readme.md"

    def test_every_platform_is_named_where_a_reader_looks_for_the_lane(self):
        text = self.page.read_text().lower()
        for name in rails.RAILS:
            self.assertIn(name, text, f"the lane page does not mention {name}")

    def test_the_microphone_rail_is_explained_rather_than_implied(self):
        text = self.page.read_text()
        for needle in ("--use-fake-device-for-media-stream", "null sink", "blackhole", "obs"):
            self.assertIn(needle, text, f"the lane page lost {needle}")

    def test_the_page_states_what_the_signature_covers(self):
        text = self.page.read_text()
        self.assertIn("covers the header and the payload", text)
        self.assertIn("nonce", text)

    def test_the_refusals_are_repeated_where_the_lane_lives(self):
        text = self.page.read_text()
        for needle in ("no cold join", "no recording"):
            self.assertIn(needle, text)


class TestTheBranchStaysDecoupled(unittest.TestCase):
    """no carrier sdk, and nothing outside the standard library except this branch's own modules."""

    # an import line, not a sentence that happens to begin with "from"
    IMPORT = re.compile(r"^(import\s+[\w.]+|from\s+[\w.]+\s+import\s)")

    def modules(self):
        """the branch's own code, tests excluded: the suite names the words it forbids."""
        for path in sorted(ROOT.rglob("*.py")):
            relative = path.relative_to(ROOT)
            if relative.parts[0] == "tests":
                continue
            yield path, relative

    def test_every_import_is_stdlib_or_here(self):
        allowed = set(sys.stdlib_module_names) | {"rails", "audio", "meetings"}
        for path, relative in self.modules():
            for line in path.read_text().splitlines():
                stripped = line.strip()
                match = self.IMPORT.match(stripped)
                if not match:
                    continue
                target = stripped.split()[1]
                if target.startswith("."):
                    continue  # a relative import is this branch by definition
                module = target.split(".")[0]
                self.assertIn(module, allowed, f"{relative} imports {module}")

    def test_no_carrier_sdk_is_named_in_an_import(self):
        for path, relative in self.modules():
            for line in path.read_text().splitlines():
                stripped = line.strip().lower()
                if not self.IMPORT.match(stripped):
                    continue
                for sdk in ("zoom", "livekit", "google", "teams", "msal"):
                    self.assertNotIn(sdk, stripped, f"{relative} pulls in {sdk}")

    def test_nothing_records_and_nothing_publishes(self):
        for path, relative in self.modules():
            text = path.read_text().lower()
            for opener in ("record(", "start_recording", "rtmp", "publish("):
                self.assertNotIn(opener, text, f"{relative} opens a {opener}")

    def test_the_pages_have_no_em_dashes(self):
        for page in sorted(ROOT.rglob("*.md")):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
