import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from docx_repro.cli import main as reduce_cli
from docx_repro.demo import TEXT, generate, make_docx
from docx_repro.demo import main as demo_cli
from docx_repro.mammoth_check import check, visible_text
from docx_repro.mammoth_check import main as check_cli

from .helpers import fixture, paragraph


class MammothDemoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="docx preset test ")
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source.docx"
        self.source.write_bytes(fixture(paragraph("TARGET PHRASE")))

    def tearDown(self):
        self.temporary.cleanup()

    def converter(self, html):
        return lambda _stream: SimpleNamespace(value=html)

    def test_preserved_text_split_by_inline_markup_is_not_missing(self):
        self.assertEqual(
            check(
                self.source,
                "TARGET PHRASE",
                converter=self.converter("<p>TARGET <strong>PHRASE</strong></p>"),
            ),
            1,
        )

    def test_text_only_in_an_attribute_is_still_missing(self):
        self.assertEqual(
            check(
                self.source,
                "TARGET PHRASE",
                converter=self.converter('<p title="TARGET PHRASE">other</p>'),
            ),
            0,
        )

    def test_deleted_source_phrase_cannot_reproduce(self):
        self.assertEqual(check(self.source, "ABSENT", converter=self.converter("<p>other</p>")), 1)

    def test_entities_and_hidden_html_are_handled(self):
        self.assertEqual(
            visible_text("<p>A&amp;B</p><script>hidden</script><style>hidden</style>"), "\nA&B\n"
        )

    def test_builtin_phrase_with_placeholder_and_leading_dashes_is_literal(self):
        phrase = "--TARGET {file}"
        data = fixture(
            '<w:p><w:dir w:val="rtl"><w:r><w:t>'
            + phrase
            + "</w:t></w:r></w:dir></w:p>"
            + paragraph("unrelated")
        )
        self.source.write_bytes(data)
        output = self.directory / "literal.docx"
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            result = reduce_cli(
                [str(self.source), "--mammoth-missing-text=" + phrase, "--out", str(output)]
            )
        self.assertEqual(result, 0)
        self.assertEqual(check(output, phrase), 0)

    def test_conversion_exception_is_inconclusive(self):
        with patch("mammoth.convert_to_html", side_effect=ValueError("unrelated")):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_cli([str(self.source), "--expect-text", "TARGET PHRASE"]), 2)

    def test_invalid_package_is_inconclusive(self):
        self.source.write_bytes(b"not a document")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_cli([str(self.source), "--expect-text", "TARGET"]), 2)

    def test_blank_phrase_rejected_before_saving_output(self):
        output = self.directory / "out.docx"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                reduce_cli([str(self.source), "--mammoth-missing-text", " ", "--out", str(output)]),
                2,
            )
        self.assertFalse(output.exists())

    def test_missing_optional_dependency_has_install_instruction(self):
        message = io.StringIO()
        with patch("docx_repro.cli.importlib.util.find_spec", return_value=None):
            with contextlib.redirect_stderr(message):
                result = reduce_cli(
                    [
                        str(self.source),
                        "--mammoth-missing-text",
                        "TARGET",
                        "--out",
                        str(self.directory / "out.docx"),
                    ]
                )
        self.assertEqual(result, 2)
        self.assertIn("docx-repro[mammoth]", message.getvalue())

    def test_generator_refuses_to_replace_existing_input(self):
        generated, _config = generate(self.directory / "demo")
        original = generated.read_bytes()
        with self.assertRaises(FileExistsError):
            generate(generated.parent)
        self.assertEqual(generated.read_bytes(), original)

    def test_demo_missing_dependency_creates_no_documents(self):
        directory = self.directory / "missing-extra"
        with patch("docx_repro.demo.importlib.util.find_spec", return_value=None):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(demo_cli([str(directory)]), 2)
        self.assertFalse(directory.exists())

    def test_built_in_checker_reduces_real_mammoth_text_loss(self):
        for wrapper in ["dir", "bdo"]:
            with self.subTest(wrapper=wrapper):
                self.source.write_bytes(make_docx(wrapper, count=9))
                output = self.directory / f"{wrapper}.docx"
                with (
                    contextlib.redirect_stderr(io.StringIO()),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(
                        reduce_cli(
                            [str(self.source), "--mammoth-missing-text", TEXT, "--out", str(output)]
                        ),
                        0,
                    )
                report = json.loads(Path(str(output) + ".repro.json").read_text())
                self.assertEqual(report["original_blocks"], 9)
                self.assertEqual(report["reduced_blocks"], 1)
                self.assertEqual(check(output, TEXT), 0)


if __name__ == "__main__":
    unittest.main()
