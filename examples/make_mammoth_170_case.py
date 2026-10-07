"""Generate original synthetic input for python-mammoth issue #170's error path."""

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

from docx_repro.demo import CONTENT_TYPES, REL, ROOT_RELS, WORD

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
RELATIONSHIP_ID = "rIdNull"
TARGET = "../NULL"


def make_docx(*, count=21, include_image=True, target=TARGET):
    if not 1 <= count <= 1000:
        raise ValueError("Choose between 1 and 1000 body blocks.")
    image = f'''<w:drawing><wp:inline>
      <wp:extent cx="914400" cy="914400"/>
      <wp:docPr id="1" name="Synthetic missing image"/>
      <a:graphic><a:graphicData uri="{PIC}"><pic:pic>
        <pic:nvPicPr><pic:cNvPr id="0" name="Synthetic image"/><pic:cNvPicPr/></pic:nvPicPr>
        <pic:blipFill><a:blip r:embed="{RELATIONSHIP_ID}"/>
          <a:stretch><a:fillRect/></a:stretch></pic:blipFill>
        <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="914400" cy="914400"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
      </pic:pic></a:graphicData></a:graphic>
    </wp:inline></w:drawing>'''
    blocks = []
    for index in range(count):
        if include_image and index == count // 2:
            content = f"<w:r><w:t>Synthetic text beside a missing image.</w:t>{image}</w:r>"
        else:
            content = f"<w:r><w:t>Unrelated synthetic paragraph {index}.</w:t></w:r>"
        blocks.append(f"<w:p>{content}</w:p>")
    document = (
        f'<w:document xmlns:w="{WORD}" xmlns:r="{REL}" xmlns:a="{A}" '
        f'xmlns:wp="{WP}" xmlns:pic="{PIC}"><w:body>'
        + "".join(blocks)
        + "<w:sectPr/></w:body></w:document>"
    )
    relationships = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="{RELATIONSHIP_ID}" Type="{REL}/image" Target={quoteattr(target)}/>'
        "</Relationships>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in {
            "[Content_Types].xml": CONTENT_TYPES,
            "_rels/.rels": ROOT_RELS,
            "word/document.xml": document,
            "word/_rels/document.xml.rels": relationships,
        }.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blocks", type=int, default=21)
    args = parser.parse_args()
    input_path = args.directory / "synthetic.docx"
    config_path = args.directory / "check.json"
    if input_path.exists() or config_path.exists():
        parser.error("Input or checker config exists; choose an empty directory.")
    try:
        document = make_docx(count=args.blocks)
    except ValueError as error:
        parser.error(str(error))
    args.directory.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(document)
    config_path.write_text(
        json.dumps(
            {
                "command": [
                    sys.executable,
                    str(Path(__file__).with_name("check_mammoth_170.py").resolve()),
                    "{file}",
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Generated {input_path} and {config_path} using original synthetic content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
