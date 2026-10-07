# Case study: isolate a flattened numbered list

This investigation uses the public DOCX attachment in [MarkItDown issue #2323](https://github.com/microsoft/markitdown/issues/2323). The attachment is not redistributed in this repository. Download it from the issue to reproduce the investigation.

The source has eight removable body paragraphs: numbered items, nested bullets, and unrelated text. The checker retains both `Item 3` and `Item 3.1`, with their original numbering properties, and accepts a candidate only when successful conversion still emits `Item 3.1` as an unindented numbered Markdown line. Removing either required paragraph rejects the candidate; unrelated exceptions are inconclusive.

Results with docx-repro 0.1.1, MarkItDown 0.1.8 (checkout `4cc9fa17653d695d64fb9eee5b33d4de55ff84e8`), Mammoth 1.13.0 and markdownify 1.2.3:

| Measurement | Original | Reduced |
| --- | ---: | ---: |
| Removable body paragraphs | 8 | 2 |
| Main document XML bytes | 5,305 | 3,469 |
| DOCX package bytes | 17,258 | 14,842 |

The search made 16 checker invocations with two confirmations per candidate, including final confirmation. Retained original indices were 4 and 5. Every other package part had identical payload bytes. This establishes a minimum under this checker's required pair and the tool's body-block constraints, not the smallest possible OOXML package.

Reduced intermediate Mammoth HTML:

```html
<ol><li>Item 3</li><li>Item 3.1</li></ol>
```

Reduced MarkItDown output:

```markdown
1. Item 3
2. Item 3.1
```

A fresh environment installed from PyPI with MarkItDown 0.1.8, its required Mammoth 1.11.0, and markdownify 1.2.3 produces the same HTML and Markdown for the reduced file. The case-specific checker returns `0` there as well. This separates the reproduction from the local checkout and confirms it with the released dependency set.

Both source paragraphs have `w:ilvl=0`, but the parent uses `numId=1` and the child uses `numId=3`. The child references a separate lower-letter numbering definition, with a 1,080-twip left indentation versus the parent's 720. The expected visual nesting is reported in the upstream issue. The reduced result shows flattening already in the Mammoth HTML, before Markdown conversion. This narrows the investigation; it does not by itself establish the correct rule for inferring semantic nesting from indentation or fix the bug.

## Reproduce the reduction

Install docx-repro from its release or checkout and install MarkItDown's DOCX dependencies in the checker environment. Save the attachment as `original.docx` and create `check.json`:

```json
{
  "command": ["python", "examples/check_markitdown_2323.py", "{file}"],
  "cwd": "/absolute/path/to/docx-repro-checkout"
}
```

Use the actual Python executable for the checker environment, especially on Windows. Then run:

```sh
docx-repro original.docx --check-config check.json --out reduced.docx
```

The checker is intentionally specific to this attachment. Numbering IDs and labels are not a general nested-list detector. The output retains supporting parts and original metadata, so review it before sharing. Reduction is not anonymization.

Input SHA-256: `9dda7e49e390df8719897a9e717aeca284f9e30ea6778bbd2c93ded7457ac766`.

Reduced SHA-256: `df1ae1c79be54e19519962f7c604eeb20e5061bd41cdf965a73eaf0b04bf26b1`.
