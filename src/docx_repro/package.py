"""Read OPC packages and remove complete body blocks without reserializing XML."""

from __future__ import annotations

import copy
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.parsers import expat

from .errors import InputError

WORD_NAMESPACES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
}
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
MAIN_PART = "word/document.xml"
BLOCK_TYPES = {"p", "tbl", "sdt", "customXml", "altChunk"}
RANGE_STARTS = {
    "bookmarkStart": "bookmark",
    "commentRangeStart": "comment",
    "moveFromRangeStart": "moveFrom",
    "moveToRangeStart": "moveTo",
    "permStart": "permission",
}
RANGE_ENDS = {
    "bookmarkEnd": "bookmark",
    "commentRangeEnd": "comment",
    "moveFromRangeEnd": "moveFrom",
    "moveToRangeEnd": "moveTo",
    "permEnd": "permission",
}


@dataclass(frozen=True)
class Limits:
    input_bytes: int = 64 * 1024 * 1024
    expanded_bytes: int = 128 * 1024 * 1024
    main_xml_bytes: int = 8 * 1024 * 1024
    entries: int = 4096


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class XmlStructure:
    blocks: tuple[Block, ...]
    range_imbalances: tuple[tuple[str, str, int], ...]


def _parser(data: bytes):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data:
        raise InputError("Only UTF-8/ASCII XML parts are supported in this release.")
    parser = expat.ParserCreate(namespace_separator="|")

    def reject(*_args):
        raise InputError("DTD and entity declarations are not supported.")

    def declaration(_version, encoding, _standalone):
        if encoding and encoding.lower().replace("_", "-") not in {"utf-8", "us-ascii"}:
            raise InputError("Only UTF-8/ASCII XML parts are supported in this release.")

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.XmlDeclHandler = declaration
    return parser


def _parse(parser, data):
    try:
        parser.Parse(data, True)
    except expat.ExpatError as error:
        raise InputError(f"Malformed XML: {error}") from error


def _name(name: str) -> tuple[str, str]:
    return tuple(name.rsplit("|", 1)) if "|" in name else ("", name)


def _tag_end(data: bytes, start: int) -> int:
    quote = 0
    for position in range(start, len(data)):
        byte = data[position]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in (34, 39):
            quote = byte
        elif byte == 62:
            return position + 1
    raise InputError("Unterminated XML tag.")


def inspect_document(data: bytes) -> XmlStructure:
    parser = _parser(data)
    stack = []
    blocks = []
    balances = {}
    bodies = 0

    def start(name, attributes):
        nonlocal bodies
        namespace, local = _name(name)
        offset = parser.CurrentByteIndex
        tag_end = _tag_end(data, offset)
        empty = data[offset:tag_end].rstrip().endswith(b"/>")
        if not stack and (namespace not in WORD_NAMESPACES or local != "document"):
            raise InputError("The main part must contain a WordprocessingML document.")
        if len(stack) == 1 and namespace in WORD_NAMESPACES and local == "body":
            bodies += 1
        candidate = (
            len(stack) == 2
            and _name(stack[-1][0])[0] in WORD_NAMESPACES
            and _name(stack[-1][0])[1] == "body"
            and namespace in WORD_NAMESPACES
            and local in BLOCK_TYPES
        )
        stack.append((name, offset, tag_end, empty, candidate))
        if namespace in WORD_NAMESPACES and local in (RANGE_STARTS.keys() | RANGE_ENDS.keys()):
            range_id = attributes.get(namespace + "|id")
            if range_id is not None:
                kind = RANGE_STARTS.get(local) or RANGE_ENDS[local]
                key = (kind, range_id)
                balances[key] = balances.get(key, 0) + (1 if local in RANGE_STARTS else -1)

    def end(_name_value):
        name, start_offset, start_end, empty, candidate = stack.pop()
        if candidate:
            end_offset = start_end if empty else _tag_end(data, parser.CurrentByteIndex)
            blocks.append(Block(start_offset, end_offset, _name(name)[1]))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    _parse(parser, data)
    if bodies != 1:
        raise InputError("The main document must contain exactly one body.")
    imbalances = tuple(
        sorted((kind, key, count) for (kind, key), count in balances.items() if count)
    )
    return XmlStructure(tuple(blocks), imbalances)


def _elements(data: bytes):
    parser = _parser(data)
    result = []
    parser.StartElementHandler = lambda name, attributes: result.append((name, attributes))
    _parse(parser, data)
    return result


@dataclass
class DocxPackage:
    original: bytes
    parts: tuple[tuple[zipfile.ZipInfo, bytes], ...]
    document: bytes
    structure: XmlStructure
    comment: bytes

    @classmethod
    def load(cls, data: bytes, limits: Limits | None = None) -> DocxPackage:
        limits = limits or Limits()
        if len(data) > limits.input_bytes:
            raise InputError("Input exceeds the compressed-size limit.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > limits.entries:
                    raise InputError("Package contains too many entries.")
                if sum(entry.file_size for entry in entries) > limits.expanded_bytes:
                    raise InputError("Package exceeds the expanded-size limit.")
                seen = set()
                parts = []
                for entry in entries:
                    path = PurePosixPath(entry.filename)
                    if (
                        entry.filename in seen
                        or entry.orig_filename != entry.filename
                        or path.is_absolute()
                        or ".." in path.parts
                        or "\\" in entry.filename
                        or ":" in entry.filename
                    ):
                        raise InputError("Package has duplicate or unsupported entry names.")
                    if entry.flag_bits & 1:
                        raise InputError("Encrypted ZIP entries are unsupported.")
                    if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                        raise InputError("Only stored and deflated ZIP entries are supported.")
                    if entry.filename.startswith("_xmlsignatures/"):
                        raise InputError(
                            "Digitally signed packages cannot retain signatures after reduction."
                        )
                    if entry.filename == MAIN_PART and entry.file_size > limits.main_xml_bytes:
                        raise InputError("Main document XML exceeds the size limit.")
                    seen.add(entry.filename)
                    parts.append((copy.copy(entry), archive.read(entry)))
                content = {entry.filename: value for entry, value in parts}
                required = {MAIN_PART, "[Content_Types].xml", "_rels/.rels"}
                if not required.issubset(content):
                    raise InputError("Expected a DOCX with word/document.xml and OPC manifests.")
                overrides = _elements(content["[Content_Types].xml"])
                if not any(
                    name == CONTENT_NS + "|Override"
                    and attrs.get("PartName") == "/" + MAIN_PART
                    and attrs.get("ContentType") == DOC_TYPE
                    for name, attrs in overrides
                ):
                    raise InputError("The package is not a supported .docx document type.")
                relationships = _elements(content["_rels/.rels"])
                main_links = [
                    attrs
                    for name, attrs in relationships
                    if name == REL_NS + "|Relationship"
                    and attrs.get("Type", "").endswith("/officeDocument")
                ]
                if (
                    len(main_links) != 1
                    or main_links[0].get("Target", "").lstrip("/") != MAIN_PART
                    or main_links[0].get("TargetMode") == "External"
                ):
                    raise InputError(
                        "The package must reference word/document.xml as its main part."
                    )
                document = content[MAIN_PART]
                structure = inspect_document(document)
                return cls(data, tuple(parts), document, structure, archive.comment)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as error:
            raise InputError(f"Cannot read DOCX package: {error}") from error

    def document_for(self, selected: tuple[int, ...]) -> bytes:
        keep = set(selected)
        pieces = []
        cursor = 0
        for index, block in enumerate(self.structure.blocks):
            pieces.append(self.document[cursor : block.start])
            if index in keep:
                pieces.append(self.document[block.start : block.end])
            cursor = block.end
        pieces.append(self.document[cursor:])
        return b"".join(pieces)

    def preserves_ranges(self, document: bytes) -> bool:
        return inspect_document(document).range_imbalances == self.structure.range_imbalances

    def build(self, document: bytes) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.comment = self.comment
            for info, content in self.parts:
                archive.writestr(
                    copy.copy(info), document if info.filename == MAIN_PART else content
                )
        return output.getvalue()
