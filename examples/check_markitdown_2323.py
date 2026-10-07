"""Recognize issue #2323's flattened numbered pair, retaining its source preconditions.

This is a case-specific checker for the attachment linked in docs/case-study-2323.md.
It intentionally retains the parent Item 3 and child Item 3.1 together.
"""

import re
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main():
    try:
        from markitdown import MarkItDown

        with zipfile.ZipFile(sys.argv[1]) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = {
            "".join(t.text or "" for t in paragraph.iter(W + "t")): paragraph
            for paragraph in document.iter(W + "p")
        }
        for label, num_id in [("Item 3", "1"), ("Item 3.1", "3")]:
            paragraph = paragraphs.get(label)
            if paragraph is None:
                return 1
            properties = paragraph.find(W + "pPr")
            if properties is None:
                return 1
            number = properties.find(f"{W}numPr/{W}numId")
            level = properties.find(f"{W}numPr/{W}ilvl")
            if number is None or level is None:
                return 1
            if number.get(W + "val") != num_id or level.get(W + "val") != "0":
                return 1
        output = MarkItDown().convert(sys.argv[1]).markdown
        return 0 if re.search(r"(?m)^\d+[.)] Item 3\.1\s*$", output) else 1
    except Exception as error:
        print(f"Inconclusive: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
