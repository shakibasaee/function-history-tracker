import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TRACKER = Path(__file__).resolve().parents[1] / "trace_history.py"
FUNCTION = """\
def calculate(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
    return total + 1
"""


class TraceHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tracker tests ")
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name)
        self.environment = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Tracker Tests")
        self.git("config", "user.email", "tracker@example.invalid")

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repository), *args],
            env=self.environment,
            text=True,
        ).strip()

    def write(self, filename, source):
        (self.repository / filename).write_text(source, encoding="utf-8")

    def commit(self, subject):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", subject)
        return self.git("rev-parse", "HEAD")[:7]

    def trace(self, filename, name):
        result = subprocess.run(
            [sys.executable, str(TRACKER), str(self.repository), filename, name],
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def assert_commits(self, report, *expected):
        self.assertEqual(re.findall(r"^Commit ([0-9a-f]+) ", report, re.MULTILINE), list(expected))

    def test_rename_in_same_file(self):
        self.write("original.py", FUNCTION)
        original = self.commit("Add calculation")
        self.write("original.py", FUNCTION.replace("calculate", "summarize"))
        rename = self.commit("Rename calculation")

        report = self.trace("original.py", "summarize")
        self.assert_commits(report, rename, original)
        self.assertIn("From original.py::calculate\nTo   original.py::summarize", report)
        self.assertIn("exact syntax-tree match", report)

    def test_move_function_without_renaming_its_file(self):
        self.write("original.py", FUNCTION)
        original = self.commit("Add calculation")
        self.write("original.py", "DEFAULT = 0\n")
        self.write("new module.py", FUNCTION)
        move = self.commit("Move calculation")
        self.write("README.md", "A calculation example.\n")
        self.commit("Document calculation")

        report = self.trace("new module.py", "calculate")
        self.assert_commits(report, move, original)
        self.assertIn("From original.py::calculate\nTo   new module.py::calculate", report)
        self.assertIn("exact syntax-tree match", report)

    def test_rename_with_a_small_code_edit(self):
        self.write("original.py", FUNCTION)
        original = self.commit("Add calculation")
        self.write("original.py", FUNCTION.replace("calculate", "summarize").replace("+ 1", "+ 2"))
        rename = self.commit("Rename calculation and adjust offset")

        report = self.trace("original.py", "summarize")
        self.assert_commits(report, rename, original)
        self.assertRegex(report, r"Match evidence: \d+\.\d% syntax-tree similarity")
        self.assertIn("-    return total + 1\n+    return total + 2", report)

    def test_ambiguous_match_lists_candidates_without_following_either(self):
        self.write("one.py", FUNCTION)
        self.write("two.py", FUNCTION.replace("calculate", "other"))
        self.commit("Add two equivalent calculations")
        self.write("one.py", "DEFAULT = 0\n")
        self.write("two.py", "DEFAULT = 0\n")
        self.write("new.py", FUNCTION.replace("calculate", "summarize"))
        ambiguous = self.commit("Replace both calculations")

        report = self.trace("new.py", "summarize")
        self.assert_commits(report, ambiguous)
        self.assertIn("History stops here. Multiple predecessors match new.py::summarize.", report)
        self.assertIn("one.py::calculate (exact syntax-tree match", report)
        self.assertIn("two.py::other (exact syntax-tree match", report)
        self.assertNotIn("Function diff", report)

    def test_copy_leaves_the_original_definition_in_place(self):
        self.write("original.py", FUNCTION)
        self.commit("Add calculation")
        self.write("original.py", "# Keep the original implementation.\n" + FUNCTION)
        self.write("copy.py", FUNCTION)
        copied = self.commit("Copy calculation")

        report = self.trace("copy.py", "calculate")
        self.assert_commits(report, copied)
        self.assertNotIn("Match evidence", report)

    def test_close_approximate_matches_are_reported_as_ambiguous(self):
        self.write("one.py", FUNCTION)
        self.write("two.py", FUNCTION.replace("+ 1", "+ 2"))
        self.commit("Add two calculation variants")
        (self.repository / "one.py").unlink()
        (self.repository / "two.py").unlink()
        self.write("new.py", FUNCTION.replace("+ 1", "+ 3"))
        ambiguous = self.commit("Replace both calculation variants")

        report = self.trace("new.py", "calculate")
        self.assert_commits(report, ambiguous)
        self.assertIn("Multiple predecessors match", report)
        self.assertRegex(report, r"one\.py::calculate \(\d+\.\d% syntax-tree similarity")
        self.assertRegex(report, r"two\.py::calculate \(\d+\.\d% syntax-tree similarity")

    def test_tiny_different_function_does_not_match_approximately(self):
        self.write("original.py", "def first():\n    return 1\n")
        self.commit("Add first function")
        self.write("original.py", "def second():\n    return 2\n")
        unrelated = self.commit("Replace first function")

        self.assert_commits(self.trace("original.py", "second"), unrelated)

    def test_merge_reports_the_original_function_edit(self):
        self.write("original.py", FUNCTION)
        original = self.commit("Add calculation")
        main = self.git("symbolic-ref", "--short", "HEAD")
        self.git("checkout", "--quiet", "-b", "change")
        self.write("original.py", FUNCTION.replace("+ 1", "+ 2"))
        edit = self.commit("Adjust offset on the branch")
        self.git("checkout", "--quiet", main)
        self.write("README.md", "Calculation example.\n")
        self.commit("Document calculation on main")
        self.git("merge", "--no-ff", "--no-edit", "change")

        report = self.trace("original.py", "calculate")
        self.assert_commits(report, edit, original)
        self.assertIn("Adjust offset on the branch", report)
