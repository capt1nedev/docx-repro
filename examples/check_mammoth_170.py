"""Recognize only the missing ../NULL embedded-image crash from Mammoth #170."""

import sys
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET

from docx_repro.package import DocxPackage

REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
EXPECTED_ERROR = "There is no item named 'word/../NULL' in the archive"


def main():
    try:
        import mammoth

        path = Path(sys.argv[1])
        package = DocxPackage.load(path.read_bytes())
        parts = {entry.filename: data for entry, data in package.parts}
        relationships = ET.fromstring(parts["word/_rels/document.xml.rels"])
        null_image_ids = {
            relationship.get("Id")
            for relationship in relationships.findall(REL_NS + "Relationship")
            if relationship.get("Type") == OFFICE_REL + "/image"
            and relationship.get("Id")
            and relationship.get("Target") == "../NULL"
            and relationship.get("TargetMode") != "External"
        }
        document = ET.fromstring(package.document)
        if not any(
            blip.get("{" + OFFICE_REL + "}embed") in null_image_ids
            for blip in document.iter(A + "blip")
        ):
            return 1
        try:
            with path.open("rb") as source:
                mammoth.convert_to_html(source)
        except KeyError as error:
            frames = traceback.extract_tb(error.__traceback__)
            in_image_reader = any(
                frame.name == "open_image" and Path(frame.filename).name == "body_xml.py"
                for frame in frames
            )
            if error.args == (EXPECTED_ERROR,) and in_image_reader:
                return 0
            raise
        return 1
    except Exception as error:
        print(f"Inconclusive: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
