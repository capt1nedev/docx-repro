"""Complement-based delta debugging over document body blocks."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass

from . import __version__
from .errors import CheckError, CheckLimit


@dataclass(frozen=True)
class ReductionResult:
    data: bytes
    report: dict


def reduce_package(package, runner, *, confirmations=2, progress=None) -> ReductionResult:
    started = time.monotonic()
    blocks = package.structure.blocks
    selected = tuple(range(len(blocks)))
    if not runner.confirm(package.original, confirmations):
        raise CheckError("Original input does not reproduce the target symptom consistently.")
    normalized = package.build(package.document)
    if not runner.confirm(normalized, confirmations):
        raise CheckError(
            "Repacking the original changes the symptom; this ZIP-level case is unsupported."
        )
    cache = {selected: True}
    range_rejections = 0
    granularity = 2
    status = "complete"

    def interesting(indices):
        nonlocal range_rejections
        if indices in cache:
            return cache[indices]
        document = package.document_for(indices)
        if not package.preserves_ranges(document):
            range_rejections += 1
            cache[indices] = False
            return False
        runner.ensure_budget(confirmations * 2 - 1, reserve_time=True)
        outcome = runner.confirm(package.build(document), confirmations)
        cache[indices] = outcome
        return outcome

    try:
        while selected:
            chunk_size = math.ceil(len(selected) / granularity)
            accepted = False
            for offset in range(0, len(selected), chunk_size):
                candidate = selected[:offset] + selected[offset + chunk_size :]
                if interesting(candidate):
                    selected = candidate
                    granularity = max(2, granularity - 1)
                    accepted = True
                    if progress:
                        progress(len(selected), runner.calls)
                    break
            if not accepted:
                if granularity >= len(selected):
                    break
                granularity = min(len(selected), granularity * 2)
    except CheckLimit as error:
        status = str(error)

    result = package.build(package.document_for(selected))
    # A cached reduction result is never the final confirmation.
    if not runner.confirm(result, confirmations):
        raise CheckError("Final candidate no longer reproduces; no output was committed.")
    report = {
        "schema_version": 1,
        "tool": "docx-repro",
        "tool_version": __version__,
        "status": status,
        "strategy": "body-block-complements",
        "original_blocks": len(blocks),
        "reduced_blocks": len(selected),
        "retained_original_indices": list(selected),
        "original_xml_bytes": len(package.document),
        "reduced_xml_bytes": len(package.document_for(selected)),
        "original_package_bytes": len(package.original),
        "reduced_package_bytes": len(result),
        "original_sha256": hashlib.sha256(package.original).hexdigest(),
        "reduced_sha256": hashlib.sha256(result).hexdigest(),
        "checker_invocations": runner.calls,
        "confirmations_per_candidate": confirmations,
        "range_guard_rejections": range_rejections,
        "all_other_part_payloads_preserved": True,
        "final_symptom_confirmed": True,
        "one_minimal_under_body_block_and_range_constraints": status == "complete",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "checker_elapsed_seconds": round(runner.elapsed_seconds, 3),
    }
    return ReductionResult(result, report)
