import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx_repro.checker import CheckConfig, CheckRunner
from docx_repro.errors import CheckError
from docx_repro.package import DocxPackage
from docx_repro.reducer import reduce_package
from examples.generate_demo import TEXT, make_docx

from .helpers import TARGET_CHECK, config, fixture, paragraph


class ReductionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="docx repro tests ")
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def runner(self, code=TARGET_CHECK, **options):
        path = config(self.directory, code)
        return CheckRunner(CheckConfig.load(path), self.directory / "candidate.docx", **options)

    def test_reduce_large_input_to_necessary_paragraph(self):
        data = fixture(
            "".join(paragraph("TARGET" if index == 100 else str(index)) for index in range(201))
        )
        package = DocxPackage.load(data)
        result = reduce_package(package, self.runner())
        self.assertEqual(result.report["reduced_blocks"], 1)
        self.assertEqual(result.report["retained_original_indices"], [100])
        self.assertTrue(result.report["one_minimal_under_body_block_and_range_constraints"])
        self.assertLess(result.report["checker_invocations"], 35)

    def test_minimization_can_keep_zero_blocks(self):
        package = DocxPackage.load(fixture(paragraph("A") + paragraph("B")))
        result = reduce_package(package, self.runner("raise SystemExit(0)"))
        self.assertEqual(result.report["reduced_blocks"], 0)

    def test_limit_saves_confirmed_result_without_minimality_claim(self):
        package = DocxPackage.load(fixture(paragraph("TARGET") + paragraph("other")))
        result = reduce_package(package, self.runner(max_checks=6))
        self.assertEqual(result.report["status"], "check_limit")
        self.assertEqual(result.report["checker_invocations"], 6)
        self.assertTrue(result.report["final_symptom_confirmed"])
        self.assertFalse(result.report["one_minimal_under_body_block_and_range_constraints"])

    def test_baseline_not_interesting_is_rejected(self):
        package = DocxPackage.load(fixture(paragraph("healthy")))
        with self.assertRaisesRegex(CheckError, "Original input"):
            reduce_package(package, self.runner())

    def test_inconsistent_checker_is_rejected(self):
        code = """from pathlib import Path
p = Path("count")
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
raise SystemExit(n % 2)
"""
        package = DocxPackage.load(fixture(paragraph("TARGET")))
        with self.assertRaisesRegex(CheckError, "inconsistent"):
            reduce_package(package, self.runner(code))

    def test_repacking_changes_are_detected_before_reduction(self):
        package = DocxPackage.load(b"ZIP PREFIX" + fixture(paragraph("TARGET")))
        code = """import sys
from pathlib import Path
raise SystemExit(0 if Path(sys.argv[1]).read_bytes().startswith(b"ZIP PREFIX") else 1)
"""
        with self.assertRaisesRegex(CheckError, "Repacking"):
            reduce_package(package, self.runner(code))

    def test_final_confirmation_is_not_cached(self):
        # Four baseline calls succeed. Reductions fail. A later final call fails.
        code = """import sys, zipfile
from pathlib import Path
p = Path("count")
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
with zipfile.ZipFile(sys.argv[1]) as archive:
    present = b"TARGET" in archive.read("word/document.xml")
raise SystemExit(0 if present and n < 5 else 1)
"""
        package = DocxPackage.load(fixture(paragraph("TARGET")))
        with self.assertRaises(CheckError):
            reduce_package(package, self.runner(code))

    def test_range_guard_retains_a_matching_bookmark_end(self):
        first = '<w:p><w:bookmarkStart w:id="1"/><w:r><w:t>TARGET</w:t></w:r></w:p>'
        second = '<w:p><w:bookmarkEnd w:id="1"/></w:p>'
        package = DocxPackage.load(fixture(first + second + paragraph("discard")))
        result = reduce_package(package, self.runner())
        self.assertEqual(result.report["reduced_blocks"], 2)
        self.assertGreater(result.report["range_guard_rejections"], 0)

    def test_current_mammoth_and_relationship_bearing_package(self):
        import mammoth

        for wrapper in ["dir", "bdo"]:
            with self.subTest(wrapper=wrapper):
                package = DocxPackage.load(make_docx(wrapper, count=21))
                checker_path = Path(__file__).parents[1] / "examples" / "check_mammoth.py"
                runner = CheckRunner(
                    CheckConfig(
                        (sys.executable, str(checker_path), "{file}", "--expect-text", TEXT),
                        self.directory,
                    ),
                    self.directory / "candidate.docx",
                )
                result = reduce_package(package, runner)
                self.assertEqual(result.report["reduced_blocks"], 1)
                converted = mammoth.convert_to_html(io.BytesIO(result.data))
                self.assertNotIn(TEXT, converted.value)
                self.assertIn('href="https://example.org/"', converted.value)
                with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
                    self.assertIsNone(archive.testzip())
