# Reduction contract

## Unit of reduction

The candidate set consists of removable top-level body blocks in `word/document.xml`. XML parsing finds byte spans; candidates concatenate unchanged byte ranges and omit selected complete spans. Root declarations, prefixes, attributes, comments, processing instructions and noncandidate body children remain unchanged.

The package writer preserves other part payloads, their order, dates, comments and compression methods. ZIP headers and compressed streams may change. Baseline checks therefore test both the original package and its repacked equivalent. A case that depends on those container differences is rejected.

## Checker

The caller defines interestingness with a command and argv arguments. A checker returning zero means the target symptom is present. One means absent. Every other result, a timeout, or modification of the candidate is inconclusive and aborts the run.

The source is copied to a fixed temporary candidate path. Checkers never receive the original path. The same path is used throughout the run to avoid changing symptoms merely through filenames. Checkers can still write elsewhere; they run with the user's permissions.

The baseline, each candidate and the final result are repeated according to the confirmation setting. Cached outcomes avoid redundant work during search, but final confirmation always executes again.

The range guard compares known marker imbalances with the original. It allows complete matched ranges to disappear, but rejects removal that introduces or changes an imbalance. It does not validate all relationships, drawing IDs, document rules or layout.

## Search and stopping

The search tries complements of increasingly small chunks of the retained blocks. An accepted candidate becomes the new working set. Once no chunk can be removed at single-block granularity, the result is one-minimal under the checker and range constraints.

Budget exhaustion can end the search earlier. Invocation budget is reserved for final confirmation. Time is also reserved, but slow or unstable checkers can still consume it; no result is saved without a successful final confirmation.

Minimality concerns removability of blocks, not compressed ZIP size. Repacking can increase bytes even after removing content. Input and output sizes are recorded so that this distinction is visible.

## Deliberate boundaries

This release reduces the document body. It keeps supporting parts, including ones no longer referenced. That makes the implementation conservative with respect to their payloads and leaves work for a later package-pruning feature. It also means body reduction cannot establish privacy or removal of all information about an original document.

The tool reports observed checker behavior. It does not prove that the checker correctly identifies a bug, that results will reproduce in another environment, or that Word renders the reduced file identically. Those properties require a suitable checker and additional tests.
