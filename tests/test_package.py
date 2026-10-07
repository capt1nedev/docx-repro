import io
import unittest
import zipfile

from docx_repro.errors import InputError
from docx_repro.package import DocxPackage, Limits, inspect_document

from .helpers import WORD, fixture, paragraph


class PackageTests(unittest.TestCase):
    def test_exact_bytes_preserve_namespace_declarations_and_markup(self):
        root = 'xmlns:mc="urn:mc" xmlns:vendor="urn:vendor" mc:Ignorable="vendor"'
        body = "<!--keep this--><?keep instruction?>" + paragraph("discard")
        target = '<w:p vendor:attr="a &gt; b"><w:r><w:t><![CDATA[TARGET]]></w:t></w:r></w:p>'
        package = DocxPackage.load(fixture(body + target, extra_root=root))
        self.assertEqual(
            package.document_for((1,)), package.document.replace(paragraph("discard").encode(), b"")
        )
        self.assertIn(root.encode(), package.document_for((1,)))

    def test_self_closing_blocks_and_quoted_angle_brackets(self):
        package = DocxPackage.load(fixture('<w:p data="&gt;"/><w:p/><w:tbl/>'))
        self.assertEqual([block.kind for block in package.structure.blocks], ["p", "p", "tbl"])
        self.assertNotIn(b"<w:tbl/>", package.document_for((0,)))
        self.assertIn(b'<w:p data="&gt;"/>', package.document_for((0,)))

    def test_strict_namespace_is_supported(self):
        xml = fixture(paragraph("TARGET"))
        with zipfile.ZipFile(io.BytesIO(xml)) as archive:
            main = archive.read("word/document.xml").replace(
                WORD.encode(), b"http://purl.oclc.org/ooxml/wordprocessingml/main"
            )
        package = DocxPackage.load(fixture("", main_xml=main))
        self.assertEqual(len(package.structure.blocks), 1)

    def test_section_properties_and_body_range_markers_are_kept(self):
        package = DocxPackage.load(
            fixture(
                '<w:bookmarkStart w:id="8"/>' + paragraph("TARGET") + '<w:bookmarkEnd w:id="8"/>'
            )
        )
        reduced = package.document_for(())
        self.assertIn(b"<w:sectPr/>", reduced)
        self.assertIn(b"bookmarkStart", reduced)
        self.assertIn(b"bookmarkEnd", reduced)

    def test_range_guard_rejects_a_new_orphan(self):
        first = '<w:p><w:bookmarkStart w:id="1"/><w:r><w:t>A</w:t></w:r></w:p>'
        second = '<w:p><w:bookmarkEnd w:id="1"/><w:r><w:t>B</w:t></w:r></w:p>'
        package = DocxPackage.load(fixture(first + second))
        self.assertFalse(package.preserves_ranges(package.document_for((0,))))
        self.assertTrue(package.preserves_ranges(package.document_for(())))

    def test_other_parts_and_metadata_are_preserved(self):
        extras = {
            "word/media/picture.bin": b"IMAGE\x00BYTES",
            "word/_rels/document.xml.rels": b"<rels/>",
        }
        package = DocxPackage.load(
            fixture(paragraph("TARGET") + paragraph("drop"), extra_parts=extras)
        )
        rebuilt = package.build(package.document_for((0,)))
        with (
            zipfile.ZipFile(io.BytesIO(package.original)) as before,
            zipfile.ZipFile(io.BytesIO(rebuilt)) as after,
        ):
            self.assertEqual(before.namelist(), after.namelist())
            self.assertEqual(before.comment, after.comment)
            for name in before.namelist():
                if name != "word/document.xml":
                    self.assertEqual(before.read(name), after.read(name))
                self.assertEqual(before.getinfo(name).comment, after.getinfo(name).comment)
                self.assertEqual(before.getinfo(name).date_time, after.getinfo(name).date_time)
                self.assertEqual(
                    before.getinfo(name).compress_type, after.getinfo(name).compress_type
                )
            self.assertIsNone(after.testzip())

    def test_reject_invalid_zip(self):
        with self.assertRaises(InputError):
            DocxPackage.load(b"not a zip")

    def test_reject_malformed_xml(self):
        with self.assertRaises(InputError):
            DocxPackage.load(fixture("", main_xml=b"<broken>"))

    def test_reject_missing_main_part(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("empty", b"")
        with self.assertRaises(InputError):
            DocxPackage.load(output.getvalue())

    def test_reject_doctype_entities_and_utf16(self):
        xml = f'<w:document xmlns:w="{WORD}"><w:body/></w:document>'
        cases = [
            ('<!DOCTYPE test [<!ENTITY x "boom">]>' + xml).encode(),
            xml.encode("utf-16"),
            ('<?xml version="1.0" encoding="ISO-8859-1"?>' + xml).encode(),
        ]
        for content in cases:
            with self.subTest(content=content[:35]), self.assertRaises(InputError):
                DocxPackage.load(fixture("", main_xml=content))

    def test_reject_traversal_and_signed_packages(self):
        for name in ["../escape", "/absolute", "word\\bad", "_xmlsignatures/sig1.xml"]:
            with self.subTest(name=name), self.assertRaises(InputError):
                DocxPackage.load(fixture("", extra_parts={name: b"ignored"}))

    def test_resource_limits(self):
        data = fixture(paragraph("hello"))
        for limits in [
            Limits(input_bytes=1),
            Limits(expanded_bytes=1),
            Limits(entries=1),
            Limits(main_xml_bytes=1),
        ]:
            with self.subTest(limits=limits), self.assertRaises(InputError):
                DocxPackage.load(data, limits)

    def test_nested_paragraphs_are_not_independent_blocks(self):
        body = "<w:tbl><w:tr><w:tc>" + paragraph("A") + "</w:tc></w:tr></w:tbl>"
        package = DocxPackage.load(
            fixture(body + "<w:sdt><w:sdtContent>" + paragraph("B") + "</w:sdtContent></w:sdt>")
        )
        self.assertEqual([block.kind for block in package.structure.blocks], ["tbl", "sdt"])

    def test_reject_multiple_bodies_and_wrong_root(self):
        for xml in [
            f'<w:document xmlns:w="{WORD}"><w:body/><w:body/></w:document>',
            "<foreign><body/></foreign>",
        ]:
            with self.subTest(xml=xml), self.assertRaises(InputError):
                inspect_document(xml.encode())
