# Synthetic reproduction of Mammoth #170's missing-image error path

[python-mammoth issue #170](https://github.com/mwilliamson/python-mammoth/issues/170) reports a `KeyError` while reading an embedded image whose relationship targets `../NULL`. The reporter cannot share the original document because it contains private information.

This case uses **original synthetic content** and the reported relationship target to reproduce the same exception path. The fixture intentionally represents an incomplete package: its embedded image part is absent. It is a robustness test for that condition. The unavailable original document was not analyzed, and the synthetic fixture cannot establish all of its contents or causes.

## Verified result

On Windows with Python 3.12.14:

| Converter | Minimal synthetic fixture |
| --- | --- |
| Mammoth 1.13.0 | `KeyError: "There is no item named 'word/../NULL' in the archive"` |
| Mammoth 1.11.0 | Same exception and `body_xml.py` / `open_image` path |

With docx-repro 0.1.2 and Mammoth 1.13.0, a 21-paragraph synthetic test document was reduced to the one paragraph containing the image reference. The final symptom was confirmed twice, with status `complete` and 18 checker invocations. Every other package part payload was retained.

The 21 paragraphs are deliberately generated test content. They are not a measurement of the private original document. The useful upstream artifact is the one-paragraph synthetic fixture and its exact checker.

- [Minimal fixture](https://github.com/capt1nedev/docx-repro/blob/main/examples/fixtures/mammoth-170.docx): 1,420 bytes; SHA-256 `447d79af149e88e91ba8383b8f3e6c6687bf34517d1db8b73c31f65bd5de3ea6`.
- [Generator](https://github.com/capt1nedev/docx-repro/blob/main/examples/make_mammoth_170_case.py).
- [Checker](https://github.com/capt1nedev/docx-repro/blob/main/examples/check_mammoth_170.py).

## Run it

Use a checkout of this repository in a virtual environment:

```sh
python -m pip install "docx-repro[demo]==0.1.2"
python examples/check_mammoth_170.py examples/fixtures/mammoth-170.docx
```

The checker exits `0` when the exact target crash occurs. To exercise reduction:

```sh
python examples/make_mammoth_170_case.py case170
docx-repro case170/synthetic.docx --check-config case170/check.json --out case170/reduced.docx
```

The generator refuses to replace existing input or configuration. It writes a checker configuration using the active Python executable, so run it in the environment containing the intended Mammoth version. `--blocks 1` generates a minimal fixture directly.

## Checker contract

The checker first validates the DOCX container and main XML. It requires an embedded DrawingML image reference whose relationship has target `../NULL` and is not external. It then runs Mammoth's normal HTML converter, including its default image handling. It accepts only the exact missing-part `KeyError` raised through the image reader.

Controls were exercised on both listed Mammoth versions:

| Candidate | Checker exit |
| --- | --- |
| Target image and crash retained | `0` |
| Target image deleted | `1` |
| A different missing image target | `1` |
| Target reference retained, but a different image fails first | `2` |
| Invalid ZIP input | `2` |

Deleting the image cannot count as a successful reproduction. Unrelated conversion failures remain inconclusive. A converter version that handles the condition without this crash returns `1`.

This investigation supplies a regression fixture and does not implement a converter fix. If a converter chooses to tolerate the incomplete package, the adjacent text available for preservation is `Synthetic text beside a missing image.` The appropriate warning and recovery policy remain an upstream decision.
