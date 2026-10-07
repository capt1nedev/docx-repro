"""Create an original synthetic DOCX for a known Mammoth text-loss case."""

import argparse
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TEXT = "REPRODUCTION TEXT MUST SURVIVE"
CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
ROOT_RELS = f'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/>
</Relationships>'''
DOCUMENT_RELS = f'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="link1" Type="{REL}/hyperlink"
    Target="https://example.org/" TargetMode="External"/>
</Relationships>'''


def make_docx(wrapper="dir", *, count=201):
    blocks = []
    for index in range(count):
        if index == count // 2:
            content = f'<w:{wrapper} w:val="rtl"><w:r><w:t>{TEXT}</w:t></w:r></w:{wrapper}>'
            content += (
                '<w:hyperlink r:id="link1"><w:r><w:t>Reference link</w:t></w:r></w:hyperlink>'
            )
        else:
            content = f"<w:r><w:t>Unrelated synthetic paragraph {index}.</w:t></w:r>"
        blocks.append(f"<w:p>{content}</w:p>")
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n<w:document xmlns:w="{WORD}" xmlns:r="{REL}">'
        + "<w:body>"
        + "".join(blocks)
        + "<w:sectPr/></w:body></w:document>"
    ).encode()
    import io

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in {
            "[Content_Types].xml": CONTENT_TYPES,
            "_rels/.rels": ROOT_RELS,
            "word/document.xml": xml,
            "word/_rels/document.xml.rels": DOCUMENT_RELS,
        }.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return output.getvalue()


def generate(directory, wrapper="dir"):
    directory.mkdir(parents=True, exist_ok=True)
    input_path = directory / "large.docx"
    config_path = directory / "check.json"
    if input_path.exists() or config_path.exists():
        raise FileExistsError("Demo input or checker config exists; choose an empty directory.")
    input_path.write_bytes(make_docx(wrapper))
    config_path.write_text(
        json.dumps(
            {
                "command": [
                    sys.executable,
                    "-m",
                    "docx_repro.mammoth_check",
                    "{file}",
                    "--expect-text",
                    TEXT,
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return input_path, config_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--wrapper", choices=["dir", "bdo"], default="dir")
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.generate_only and importlib.util.find_spec("mammoth") is None:
        print('Install the demo with: pip install "docx-repro[demo]"', file=sys.stderr)
        return 2
    output = args.directory / "reduced.docx"
    try:
        if not args.generate_only and (
            output.exists() or Path(str(output) + ".repro.json").exists()
        ):
            raise FileExistsError("Demo output exists; choose an empty directory.")
        input_path, config_path = generate(args.directory, args.wrapper)
    except OSError as error:
        print(f"docx-repro-demo: {error}", file=sys.stderr)
        return 2
    print(f"Generated {input_path} and {config_path} using synthetic content.")
    if args.generate_only:
        return 0
    from .cli import main as reduce_cli

    return reduce_cli([str(input_path), "--mammoth-missing-text", TEXT, "--out", str(output)])


if __name__ == "__main__":
    raise SystemExit(main())
