import io
import json
import sys
import zipfile
from pathlib import Path

from examples.generate_demo import CONTENT_TYPES, ROOT_RELS, WORD


def fixture(body, *, extra_root="", extra_parts=None, main_xml=None, comment=b"original comment"):
    xml = (
        main_xml
        or (
            f'<w:document xmlns:w="{WORD}" {extra_root}><w:body>'
            + body
            + "<w:sectPr/></w:body></w:document>"
        ).encode()
    )
    parts = {
        "[Content_Types].xml": CONTENT_TYPES.encode(),
        "_rels/.rels": ROOT_RELS.encode(),
        "word/document.xml": xml,
        **(extra_parts or {}),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.comment = comment
        for index, (name, content) in enumerate(parts.items()):
            info = zipfile.ZipInfo(name, date_time=(2025, 4, 5, 6, 7, 8))
            # Preserve crafted names even where ZipInfo normalizes platform separators.
            info.filename = name
            info.orig_filename = name
            info.comment = b"part metadata"
            info.compress_type = zipfile.ZIP_STORED if index % 2 else zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()


def paragraph(text):
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def config(directory: Path, code: str, *, arguments=None):
    checker = directory / "checker with spaces.py"
    checker.write_text(code, encoding="utf-8")
    path = directory / "check.json"
    path.write_text(
        json.dumps({"command": [sys.executable, str(checker), "{file}", *(arguments or [])]}),
        encoding="utf-8",
    )
    return path


TARGET_CHECK = """import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    xml = archive.read("word/document.xml")
sys.exit(0 if b"TARGET" in xml else 1)
"""
