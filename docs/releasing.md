# Release publishing

PyPI publishing is configured through a pending Trusted Publisher once the maintainer has a verified PyPI account with two-factor authentication. Registration, authentication and CAPTCHA steps remain under the account owner's control.

Exact publisher fields:

| Field | Value |
| --- | --- |
| PyPI project name | `docx-repro` |
| GitHub owner | `capt1nedev` |
| Repository | `docx-repro` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

Add the publisher at <https://pypi.org/manage/account/publishing/>. A pending publisher does not reserve the package name. The first successful upload creates the project owned by the PyPI account that registered the publisher.

The publishing workflow verifies the selected tag with the Windows/Linux test matrix. A separate build job checks that the tag matches the package version, builds wheel and source archives, checks metadata with Twine, and uploads an immutable artifact. The publishing job receives only that artifact, with the `id-token: write` permission needed for PyPI authentication. No stored PyPI API token is required.

Releases named `vVERSION` trigger validation when published. Automatic uploads are enabled after account setup by setting the repository variable `PYPI_ENABLED` to `true`. A manually dispatched run can validate a tag without uploading (the default) or upload a tag after account setup. An unsuccessful upload can be retried with the same unchanged artifacts/version; PyPI rejects replacing already uploaded files. Inspect whether either archive was uploaded before retrying a partially completed upload.

Version changes must update `pyproject.toml`, `src/docx_repro/__init__.py` and the changelog. Install from PyPI in a fresh environment after publishing and run `docx-repro-demo` to verify the public distribution.

References: [PyPI pending publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/), [publishing workflow](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
