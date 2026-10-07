# docx-repro

Reduce a DOCX parser bug report to the body content that still reproduces it.

Give `docx-repro` a document and a checker that recognizes your exact problem. It removes complete body blocks, tests each candidate, and saves a smaller document only after confirming the symptom again. The original file is preserved.

**Status:** first alpha release. Core installation has no runtime dependencies. Python 3.10+.

## Why use it?

An extraction bug can hide in one paragraph of a large document. Manually deleting unrelated content is tedious, and an invalid replacement document can demonstrate a different problem. This tool automates the deletion-and-check loop.

The reducer edits the original `word/document.xml` bytes. It retains namespace declarations, document attributes, section properties, and the payload of every other package part, including styles, images and relationships. Original ZIP container bytes are not retained: the package is repacked and tested before reduction starts.

## Install

From [PyPI](https://pypi.org/project/docx-repro/):

```sh
python -m pip install docx-repro
docx-repro --version
```

From a checkout:

```sh
python -m pip install .
docx-repro --version
```

From GitHub:

```sh
python -m pip install "git+https://github.com/capt1nedev/docx-repro.git@v0.1.2"
```

Release wheels can also be installed directly from the [GitHub release](https://github.com/capt1nedev/docx-repro/releases/tag/v0.1.2).

## Runnable example: missing text in Mammoth

The demo uses original synthetic content and a documented `w:dir` text-loss case. It includes an external hyperlink relationship. Mammoth 1.13.0 is pinned so the example is reproducible; later converter versions may fix this symptom.

In a virtual environment, these two commands install and run the complete demo. No checkout or custom checker is needed:

```sh
python -m pip install "docx-repro[demo]==0.1.2"
docx-repro-demo demo
```

The input has 201 body blocks. On the tested Mammoth version, the output retains the one paragraph that still loses the specified text. The report is written to `demo/reduced.docx.repro.json`.

Generate a second example with `--wrapper bdo` in a different directory. The checker rejects candidates that deleted the expected text from the source, and treats conversion exceptions as inconclusive.

The demo command generates the source, checker config, reduced document and report. It refuses to replace existing demo files. `--generate-only` generates the source and config without running Mammoth.

For an external bug report, the [MarkItDown nested-list case study](https://github.com/capt1nedev/docx-repro/blob/v0.1.2/docs/case-study-2323.md) reduces eight paragraphs to the two needed by its checker and examines the intermediate HTML.

This example isolates text preservation; it does not validate full bidirectional layout semantics or prove that a reduced file renders identically in Word.

## Check missing text in your own document

Install the `mammoth` extra, then select a literal phrase within one paragraph that should survive conversion:

```sh
python -m pip install "docx-repro[mammoth]"
docx-repro input.docx --mammoth-missing-text "Expected phrase" --out reduced.docx
```

This checker requires the phrase in source paragraph text and its absence from visible Mammoth HTML after a successful conversion. It handles inline markup and HTML entities. It does not infer intended styling, normalize whitespace, or check headers and other package parts. Use `--check-config` for other symptoms or converters.

The `demo` extra pins Mammoth 1.13.0; the `mammoth` extra accepts 1.11.0 or later. A newer converter may fix the bug you are investigating. Run the check against the version relevant to your report. MarkItDown 0.1.8 pins Mammoth 1.11.x, so use its checker environment for that case and a separate environment for the 1.13.0 demo.

## Use your own checker

Create a JSON file:

```json
{
  "command": ["python", "check_bug.py", "{file}"],
  "cwd": "."
}
```

`cwd` defaults to the configuration file's directory. Relative paths are resolved there. `{file}` is replaced with an absolute path to a temporary candidate, and arguments are passed directly without a shell. Commands may invoke a converter written in any language.

Checker exit codes:

| Code | Meaning | Reducer action |
| --- | --- | --- |
| `0` | The specific target symptom still occurs | May retain the candidate |
| `1` | The target symptom does not occur | Reject the candidate |
| Any other code, including `2` | Cannot assess, or checker failed | Stop without committing a result |

The checker must be read-only and must not prompt for input. Its stdout and stderr are discarded to keep repeated runs bounded. Run it directly if you need diagnostics. On Windows, use a direct executable such as `python.exe`; batch-file entry points are rejected.

**Define the symptom carefully.** For missing text, require that the text remains in the source and conversion completes before testing whether the output omits it. For a particular crash, verify its signature and preconditions instead of accepting every nonzero converter exit.

Checkers are programs you choose to run. They inherit your environment and permissions; this tool is not a sandbox. The core reducer does not fetch external document relationships or call a network service.

## Limits and reports

```sh
docx-repro input.docx --check-config check.json --out small.docx \
  --max-checks 200 --timeout 10 --max-seconds 300 --confirmations 2
```

Use one line on Windows PowerShell. By default, each checker result is repeated twice; the original, repacked original and final candidate are also confirmed. This detects some unstable checkers, not all nondeterminism.

- `--max-checks`: total checker invocations, including confirmations.
- `--timeout`: seconds per checker invocation. A timeout is inconclusive and stops the run.
- `--max-seconds`: total time budget. Time is reserved for final confirmation; expiration can stop the run.
- `--confirmations`: repeat each result 1–5 times; default 2.
- `--report`: optional report path; default is the output path plus `.repro.json`.
- `--force`: replace existing output files. The source and checker config remain protected.
- `--quiet`: suppress normal progress output.

CLI exit `0` means a confirmed result was saved; `2` means an input, checker or output error; `130` means interrupted. A successful report can have status `check_limit` or `time_limit`: the saved result is confirmed, but minimality was not established. Check `status` rather than assuming every successful run exhausted the search.

Reports include retained original block indices, sizes, hashes, invocation counts, confirmation settings, and whether the search completed under its constraints. They exclude document text, full checker commands and environment values.

With status `complete`, no single retained body block can be removed while satisfying the range guard and the observed checker result. This is a constrained local minimum, not a guarantee of the globally smallest file or fewest ZIP bytes.

## Scope and limitations

- Removes whole top-level paragraphs, tables, content controls, custom XML blocks and `altChunk` blocks. It does not minimize individual runs, rows or package parts.
- Retains unrecognized body children and section properties. A range guard prevents introducing a new imbalance in common bookmark, comment, move and permission start/end markers.
- Supports standard DOCX packages with `word/document.xml`, UTF-8/ASCII XML, and stored/deflated ZIP entries. Digitally signed packages, encrypted entries, DTD/entity declarations, malformed main XML and unsupported main-part locations are rejected.
- Input limits are 64 MiB compressed, 128 MiB expanded, 8 MiB main XML and 4,096 ZIP entries.
- Preserving package payloads is not a proof of complete OOXML validity, identical layout or application compatibility. The checker must verify the properties relevant to your reproduction.
- The two output files are committed separately. If a filesystem error occurs while saving the report, the confirmed DOCX can already exist; examine the error before rerunning.

**Reduction is not anonymization.** Other package parts and ZIP metadata are retained, so removed body content can leave personal information in comments, headers, properties, images or unused parts. Review a reduced package before sharing it.

## Development

```sh
python -m pip install -e ".[dev,demo]"
python -m unittest discover -s tests -t . -v
ruff check .
ruff format --check .
python -m build
```

The CI workflow builds and installs the wheel, runs the suite, and exercises the demo on Windows and Linux with Python 3.10 and 3.13. Local release checks also exercise the installed wheel in a fresh environment.

Release publishing uses GitHub Actions and PyPI Trusted Publishing. See [the release guide](https://github.com/capt1nedev/docx-repro/blob/v0.1.2/docs/releasing.md) for the configured repository, workflow and environment.

See [CONTRIBUTING.md](https://github.com/capt1nedev/docx-repro/blob/v0.1.2/CONTRIBUTING.md) for useful contribution cases and [docs/design.md](https://github.com/capt1nedev/docx-repro/blob/v0.1.2/docs/design.md) for the reduction contract.

## Background and maintenance

Delta debugging is an established technique; [Picire](https://github.com/renatahodovan/picire) is a general implementation. This project independently implements a DOCX-specific workflow. The runnable example is motivated by [Mammoth issue #490](https://github.com/mwilliamson/mammoth.js/issues/490); it is not affiliated with or endorsed by Mammoth.

Maintained by [capt1nedev](https://github.com/capt1nedev). Initial implementation was developed with Codex assistance and checked using executable tests and parser reproductions. Bugs, scope corrections and small reproducible cases are welcome.

MIT licensed.
