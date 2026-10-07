"""0: expected source text is missing from HTML; 1: not reproduced; 2: inconclusive.

This checker defines one specific symptom. It rejects candidates that simply
delete the expected phrase, and rejects unrelated conversion exceptions.
"""

import argparse
import io
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--expect-text", required=True)
    args = parser.parse_args()
    try:
        import mammoth

        data = args.file.read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
        text = "".join(
            element.text or ""
            for element in document.iter()
            if element.tag.rsplit("}", 1)[-1] == "t"
        )
        if args.expect_text not in text:
            return 1
        converted = mammoth.convert_to_html(io.BytesIO(data))
        from html import escape

        return 0 if escape(args.expect_text, quote=False) not in converted.value else 1
    except Exception as error:
        print(f"Inconclusive: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
