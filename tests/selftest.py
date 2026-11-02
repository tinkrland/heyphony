"""setup branch selftests: stdlib only. run: python3 tests/selftest.py

this branch is instructions, so the tests are about the instructions. modes.py holds the facts and
readme.md argues from them, and a comparison table in a page is the kind of thing that quietly
becomes false six months later. every cell here is checked against the dict, and every heading in
the page is checked against the host that owns it.
"""
import contextlib
import io
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import modes

HEADER = {
    "registration_survives_sleep": "registration survives sleep",
    "calls_while_asleep": "calls while asleep",
    "texts_while_asleep": "texts while asleep",
    "secret_leaves_disk": "secret leaves your disk",
    "inbound_port": "inbound port needed",
}


def readme():
    return (ROOT / "readme.md").read_text()


def table_rows(text):
    """the comparison table, as (label, [cells]) so a cell can be compared rather than eyeballed."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("|  |"))
    rows = []
    for line in lines[start + 2:]:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append((cells[0], cells[1:]))
    return lines[start], rows


class TestTheThreeModesAreTheThreeModes(unittest.TestCase):
    def test_exactly_three_modes_and_they_are_the_ones_asked_for(self):
        self.assertEqual(sorted(modes.MODES), ["local", "own-vm", "spawnable"])
        self.assertEqual([modes.MODES[m]["row"] for m in ("local", "own-vm", "spawnable")],
                         ["a computer you own", "a computer of its own", "a spawnable"])

    def test_every_mode_places_all_three_things(self):
        """the whole branch is one question asked three ways: where the registration, the secret and the catcher sit."""
        for name, entry in modes.MODES.items():
            for key in ("registration", "secret", "catcher", "where", "why", "cost", "depends_on"):
                self.assertTrue(entry.get(key), f"{name} does not say its {key}")

    def test_a_local_answer_asks_which_computer_before_it_answers(self):
        answer = modes.plan("local")
        self.assertEqual(answer["needs"], "host")
        self.assertEqual(answer["flag"], "--host")
        self.assertEqual(sorted(answer["options"]), sorted(modes.HOSTS))
        self.assertIn("which computer", answer["why"])

    def test_an_own_vm_answer_asks_which_housing(self):
        answer = modes.plan("own-vm")
        self.assertEqual(answer["needs"], "housing")
        self.assertEqual(sorted(answer["options"]), sorted(modes.HOUSING))

    def test_the_spawnable_mode_never_puts_the_registration_in_the_burn(self):
        """the one claim this branch exists to get right."""
        entry = modes.MODES["spawnable"]
        self.assertIn("never in the body that gets shredded", entry["registration"])
        self.assertIn("holds no credential", entry["secret"])
        self.assertFalse(entry["secret_leaves_disk"])
        self.assertEqual(entry["registration_survives_sleep"], "only with a duty cycle")
        self.assertEqual(entry["calls_while_asleep"], "only in the window")

    def test_every_mode_names_the_two_human_acts(self):
        for name in modes.MODES:
            answer = modes.plan(name, {"local": "macos", "own-vm": "cloud-vm"}.get(name))
            human = " ".join(answer["human"])
            self.assertIn("pay", human, f"{name} pretends nobody pays for the number")
            self.assertIn("sip username", human, f"{name} pretends nobody fetches the credential")

    def test_every_errand_proves_itself_with_one_real_message(self):
        for name, host in (("local", "macos"), ("own-vm", "cloud-vm"), ("spawnable", None)):
            answer = modes.plan(name, host)
            steps = " ".join(answer["steps"])
            self.assertIn("heyphony", steps, f"{name} does not name a command")
            self.assertIn("doctor", steps, f"{name} does not say how to check")
            self.assertIn("real message", steps, f"{name} never proves the lane")

    def test_the_guest_reads_the_inbox_and_never_the_secret(self):
        steps = " ".join(modes.plan("spawnable")["steps"])
        self.assertIn("open messages --unread", steps)
        self.assertIn("never copy the sip secret", steps)
        self.assertIn("--on guest", steps, "the one honest use of a guest registration is proving it")

    def test_an_unknown_mode_names_the_ones_that_exist(self):
        with self.assertRaises(KeyError) as raised:
            modes.mode("kubernetes")
        self.assertIn("spawnable", str(raised.exception))


class TestTheReadmeAndTheDataAgree(unittest.TestCase):
    def test_each_mode_has_its_own_section_with_its_label(self):
        text = readme()
        for number, name in (("one", "local"), ("two", "own-vm"), ("three", "spawnable")):
            self.assertIn(f"## mode {number}: {modes.MODES[name]['label']}",
                          text, f"mode {number} lost its heading")

    def test_every_computer_in_the_local_mode_is_on_the_page(self):
        text = readme().lower()
        for name, entry in modes.HOSTS.items():
            for needle in entry["points"]:
                self.assertIn(needle.lower(), text, f"{name} lost {needle!r} from the page")

    def test_every_housing_in_the_own_vm_mode_is_on_the_page(self):
        text = readme().lower()
        for name, entry in modes.HOUSING.items():
            for needle in entry["points"]:
                self.assertIn(needle.lower(), text, f"{name} lost {needle!r} from the page")

    def test_the_comparison_table_is_the_dict_cell_by_cell(self):
        header, rows = table_rows(readme())
        for column, label in HEADER.items():
            self.assertIn(label, header, f"the table lost the {label!r} column")
        self.assertEqual(len(rows), len(modes.MODES), "the table has a row per mode, or it is wrong")
        by_row = {row: cells for row, cells in rows}
        for mode_name, entry in modes.MODES.items():
            self.assertIn(entry["row"], by_row, f"{entry['row']} has no row")
            cells = by_row[entry["row"]]
            for index, column in enumerate(HEADER):
                self.assertEqual(cells[index], entry["cells"][column],
                                 f"{mode_name}.{column} drifted from the page")

    def test_a_cell_cannot_contradict_the_fact_behind_it(self):
        """the table is prose and the dict is data, so the first word of a cell has to agree."""
        for name, entry in modes.MODES.items():
            for column, cell in entry["cells"].items():
                fact = entry[column]
                expected = ("yes" if fact else "no") if isinstance(fact, bool) else str(fact)
                self.assertTrue(cell.startswith(expected),
                                f"{name}.{column} says {cell!r} while the fact says {fact!r}")

    def test_the_shared_facts_are_stated_once_for_all_three(self):
        text = readme().lower()
        for needle in ("a dollar a month", "classified as voip", "the same command",
                       "paying for the number", "sip password", "0600"):
            self.assertIn(needle, text, f"the shared section lost {needle!r}")

    def test_the_page_says_which_computer_is_the_whole_question(self):
        text = readme()
        self.assertIn("which computer", text)
        self.assertIn("which computer", modes.MODES["local"]["depends_on"],
                      "the mode whose answer depends on the machine has to say so in its data too")

    def test_no_page_picked_up_an_em_dash(self):
        for page in ROOT.rglob("*.md"):
            self.assertNotIn("\u2014", page.read_text(), f"{page.name} has an em dash")

    def test_the_byline_is_the_one_this_branch_means(self):
        self.assertIn("*three modes, one question, and the two of them that answer it honestly*", readme())


class TestThisBranchStaysAnOrphan(unittest.TestCase):
    """an orphan describes where the package runs. it must not become a second copy of it."""

    def test_nothing_here_imports_the_package(self):
        for path in ROOT.rglob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    self.assertNotIn("heyphony", stripped, f"{path.name} imports the package")

    def test_only_the_standard_library_is_imported(self):
        allowed = {"argparse", "contextlib", "io", "json", "pathlib", "re", "sys", "unittest", "modes"}
        for path in ROOT.rglob("*.py"):
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("import ", "from ")):
                    module = stripped.split()[1].split(".")[0]
                    self.assertIn(module, allowed, f"{path.name} imports {module}")

    def test_the_package_itself_is_not_copied_into_this_branch(self):
        for leftover in ("heyphony", "bin", "npm"):
            self.assertFalse((ROOT / leftover).exists(), f"{leftover}/ belongs on main, not here")

    def test_the_planner_runs_where_nothing_else_does(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = modes.main(["--compare"])
        self.assertEqual(code, 0)
        self.assertIn("rows", json.loads(buffer.getvalue()))

    def test_the_page_points_at_the_planner_and_at_main(self):
        text = readme()
        self.assertIn("python3 modes.py --compare", text)
        self.assertIn("python3 modes.py --mode local --host macos", text)
        self.assertIn("tinkrland/heyphony/main/npm/install.sh", text,
                      "the instructions have to say how to install the thing they configure")

    def test_the_branch_lists_itself_before_it_starts_instructioning(self):
        text = readme()
        self.assertIn("the three things every mode has to place", text)
        for needle in ("the registration", "the secret", "the catcher"):
            self.assertIn(needle, text, f"the nouns section lost {needle!r}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"selftest: {result.testsRun - failed}/{result.testsRun} pass")
    sys.exit(1 if failed else 0)
