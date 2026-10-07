"""Recognize a missing phrase after a successful Mammoth conversion.

0: symptom reproduced; 1: absent or deleted from source; 2: inconclusive.
"""

from __future__ import annotations

import argparse
import base64
import io
import sys
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .package import WORD_NAMESPACES, DocxPackage, Limits


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments = []
        self.hidden = 0

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {
            "p",
            "div",
            "li",
            "tr",
            "br",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self.fragments.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {
            "p",
            "div",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }:
            self.fragments.append("\n")

    def handle_data(self, text):
        if not self.hidden:
            self.fragments.append(text)


def visible_text(html):
    parser = _VisibleText()
    parser.feed(html)
    parser.close()
    return "".join(parser.fragments)


def source_text(document):
    root = ET.fromstring(document)
    paragraphs = []
    for paragraph in root.iter():
        if paragraph.tag not in {f"{{{namespace}}}p" for namespace in WORD_NAMESPACES}:
            continue
        fragments = []
        for element in paragraph.iter():
            if element.tag in {f"{{{namespace}}}t" for namespace in WORD_NAMESPACES}:
                fragments.append(element.text or "")
            elif element.tag in {f"{{{namespace}}}tab" for namespace in WORD_NAMESPACES}:
                fragments.append("\t")
            elif element.tag in {f"{{{namespace}}}br" for namespace in WORD_NAMESPACES}:
                fragments.append("\n")
        paragraphs.append("".join(fragments))
    return "\n".join(paragraphs)


def check(path, expected, *, converter=None):
    if not expected.strip():
        raise ValueError("Expected text must contain a non-whitespace character.")
    if path.stat().st_size > Limits().input_bytes:
        raise ValueError("Input exceeds the compressed-size limit.")
    data = path.read_bytes()
    package = DocxPackage.load(data)
    if expected not in source_text(package.document):
        return 1
    if converter is None:
        import mammoth

        converter = mammoth.convert_to_html
    converted = converter(io.BytesIO(data))
    return 0 if expected not in visible_text(converted.value) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    expected = parser.add_mutually_exclusive_group(required=True)
    expected.add_argument("--expect-text")
    expected.add_argument("--expect-text-base64", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        phrase = args.expect_text
        if args.expect_text_base64 is not None:
            phrase = base64.b64decode(args.expect_text_base64, validate=True).decode("utf-8")
        return check(args.file, phrase)
    except Exception as error:
        print(f"Inconclusive: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
