# Changelog

## 0.1.2

- Use the live PyPI package in installation and runnable demo instructions.
- Fix documentation links in the README rendered on PyPI.
- Document the active Trusted Publishing configuration. Reducer behavior is unchanged.

## 0.1.1

- Packaged `docx-repro-demo` command: generate and reduce synthetic input from an installed wheel.
- Built-in `--mammoth-missing-text` checker with source-text and visible-HTML confirmation.
- Preserve phrases split by inline HTML markup and reject text found only in attributes.
- Optional Mammoth dependency, wheel installation instructions and Trusted Publishing workflow.

## 0.1.0

- DOCX body-block reduction with namespace-preserving byte edits.
- Explicit checker protocol, repeated confirmation, process timeouts and invocation limits.
- Retained supporting part payloads and common range-marker guard.
- JSON evidence reports, source protection and refusal to overwrite outputs by default.
- Original synthetic Mammoth text-loss examples and automated tests.
