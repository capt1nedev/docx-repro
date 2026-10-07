"""Generate the packaged demonstration without running the reducer."""

import sys

from docx_repro.demo import CONTENT_TYPES, ROOT_RELS, TEXT, WORD, main, make_docx  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main([*sys.argv[1:], "--generate-only"]))
