# Contributing

Useful contributions begin with a reproducible case: a reduction that changes the intended symptom, an incorrect range rejection, an unsupported but legitimate package, or a checker lifecycle problem.

Use synthetic documents or a document you have permission to share. A generated fixture plus the exact checker is preferable to a confidential attachment. Include Python version, platform, tool version, command, and the report when available. Review the report and package before uploading either.

Before opening a large feature PR, describe the use case in an issue. For fixes, add a regression case showing the behavior before and after the change. Preserve namespace bytes and other package payloads; changing serializers is a behavior change.

Run the commands in the README's Development section. New code should work on Python 3.10+ and avoid adding a dependency unless it solves a demonstrated need.

AI-assisted contributions are welcome. Describe your validation and take responsibility for the result. Do not include tokens, private files, or content without permission in a patch.

Contributions are released under the project's MIT license. The maintainer reviews issues and changes; contributor recognition reflects substantive work rather than counts of small edits.
