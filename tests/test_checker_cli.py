import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from docx_repro.checker import CheckConfig, CheckRunner
from docx_repro.cli import main
from docx_repro.errors import CheckError, InputError

from .helpers import TARGET_CHECK, config, fixture, paragraph


class CheckerCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="docx cli test ")
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source.docx"
        self.data = fixture(paragraph("TARGET") + paragraph("unrelated"))
        self.source.write_bytes(self.data)
        self.output = self.directory / "reduced.docx"
        self.config = config(self.directory, TARGET_CHECK)

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *extra, output=None):
        arguments = [
            str(self.source),
            "--check-config",
            str(self.config),
            "--out",
            str(output or self.output),
            "--quiet",
            *extra,
        ]
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            return main(arguments)

    def runner(self, code):
        path = config(self.directory, code)
        return CheckRunner(CheckConfig.load(path), self.directory / "candidate.docx")

    def test_cli_outputs_report_and_preserves_source(self):
        self.assertEqual(self.cli(), 0)
        report = json.loads(Path(str(self.output) + ".repro.json").read_text())
        self.assertEqual(report["reduced_blocks"], 1)
        self.assertEqual(self.source.read_bytes(), self.data)
        self.assertNotIn("command", report)

    def test_existing_output_is_not_overwritten(self):
        self.output.write_bytes(b"existing")
        self.assertEqual(self.cli(), 2)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_force_cannot_overwrite_source(self):
        self.assertEqual(self.cli("--force", output=self.source), 2)
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_force_cannot_overwrite_checker_config(self):
        original = self.config.read_bytes()
        self.assertEqual(self.cli("--force", output=self.config), 2)
        self.assertEqual(self.config.read_bytes(), original)

    def test_force_replaces_existing_output(self):
        self.output.write_bytes(b"existing")
        self.assertEqual(self.cli("--force"), 0)
        self.assertNotEqual(self.output.read_bytes(), b"existing")

    def test_report_and_docx_cannot_be_the_same_file(self):
        self.assertEqual(self.cli("--report", str(self.output)), 2)

    def test_hardlink_to_source_is_protected(self):
        os.link(self.source, self.output)
        self.assertEqual(self.cli("--force"), 2)
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_unknown_checker_exit_produces_no_output(self):
        self.config = config(self.directory, "raise SystemExit(2)")
        self.assertEqual(self.cli(), 2)
        self.assertFalse(self.output.exists())

    def test_checker_input_mutation_is_rejected(self):
        runner = self.runner(
            'import sys; from pathlib import Path; Path(sys.argv[1]).write_bytes(b"changed")'
        )
        with self.assertRaisesRegex(CheckError, "changed"):
            runner.check(self.data)

    def test_checker_timeout_is_inconclusive(self):
        runner = self.runner("import time; time.sleep(5)")
        runner.timeout = 0.1
        with self.assertRaisesRegex(CheckError, "timed out"):
            runner.check(self.data)

    def test_timeout_terminates_a_checker_child_process(self):
        child_code = (
            "import time; from pathlib import Path; time.sleep(1.2); "
            'Path("orphan-marker").write_text("bad")'
        )
        code = (
            "import subprocess, sys, time\nfrom pathlib import Path\n"
            f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
            "Path('child-started').write_text(str(child.pid))\ntime.sleep(5)\n"
        )
        runner = self.runner(code)
        runner.timeout = 0.5
        with self.assertRaisesRegex(CheckError, "timed out"):
            runner.check(self.data)
        self.assertTrue((self.directory / "child-started").exists())
        time.sleep(1.0)
        self.assertFalse((self.directory / "orphan-marker").exists())

    def test_spaces_and_shell_characters_are_literal_arguments(self):
        marker = "literal ; $() and spaces"
        self.config = config(
            self.directory,
            "import sys; raise SystemExit(0 if sys.argv[2] == 'literal ; $() and spaces' else 2)",
            arguments=[marker],
        )
        runner = CheckRunner(CheckConfig.load(self.config), self.directory / "candidate.docx")
        self.assertTrue(runner.check(self.data))

    def test_invalid_configs_fail_before_execution(self):
        for value in [
            {"command": "python script.py"},
            {"command": ["python", "script.py"]},
            {"command": ["{file}", "argument"]},
            {"command": ["python", "{file}"], "unexpected": True},
            {"command": ["python", "{file}"], "cwd": 42},
        ]:
            with self.subTest(value=value):
                self.config.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(InputError):
                    CheckConfig.load(self.config)

    def test_relative_executable_resolves_from_config_directory(self):
        relative_executable = os.path.relpath(sys.executable, self.directory)
        self.config.write_text(
            json.dumps({"command": [relative_executable, "-c", "raise SystemExit(0)", "{file}"]}),
            encoding="utf-8",
        )
        loaded = CheckConfig.load(self.config)
        self.assertEqual(Path(loaded.command[0]).resolve(), Path(sys.executable).resolve())
        runner = CheckRunner(loaded, self.directory / "candidate.docx")
        self.assertTrue(runner.check(self.data))

    def test_insufficient_check_budget_is_rejected(self):
        self.assertEqual(self.cli("--max-checks", "5"), 2)
        self.assertFalse(self.output.exists())

    def test_missing_output_directory_is_not_created(self):
        self.assertEqual(self.cli(output=self.directory / "missing" / "out.docx"), 2)

    def test_missing_executable_is_a_checker_error(self):
        runner = CheckRunner(
            CheckConfig(("definitely-not-a-docx-checker", "{file}"), self.directory),
            self.directory / "candidate.docx",
        )
        with self.assertRaisesRegex(CheckError, "Cannot start"):
            runner.check(self.data)
