from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import math
import os
import sys
import tempfile
from pathlib import Path

from . import __version__
from .checker import CheckConfig, CheckRunner
from .errors import CheckLimit, InputError, ReproError
from .package import DocxPackage, Limits
from .reducer import reduce_package


def _positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def parser():
    arguments = argparse.ArgumentParser(
        description="Shrink a DOCX while an explicit checker confirms the same parser symptom."
    )
    arguments.add_argument("input", type=Path)
    checks = arguments.add_mutually_exclusive_group(required=True)
    checks.add_argument("--check-config", type=Path)
    checks.add_argument(
        "--mammoth-missing-text",
        metavar="PHRASE",
        help="built-in check: PHRASE remains in document text but is missing from Mammoth HTML",
    )
    arguments.add_argument("--out", required=True, type=Path)
    arguments.add_argument("--report", type=Path, help="default: OUTPUT.docx.repro.json")
    arguments.add_argument("--timeout", type=_positive, default=10.0, help="seconds per checker")
    arguments.add_argument("--max-seconds", type=_positive, default=300.0)
    arguments.add_argument("--max-checks", type=int, default=200)
    arguments.add_argument("--confirmations", type=int, choices=range(1, 6), default=2)
    arguments.add_argument("--force", action="store_true", help="replace existing output files")
    arguments.add_argument("--quiet", action="store_true")
    arguments.add_argument("--version", action="version", version=__version__)
    return arguments


def _same_path(first, second):
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and os.path.samefile(first, second)


def _check_destinations(args, report):
    paths = [path for path in [args.input, args.check_config, args.out, report] if path is not None]
    for index, path in enumerate(paths):
        if any(_same_path(path, other) for other in paths[index + 1 :]):
            raise InputError(
                "Input, checker config, DOCX output and report must be distinct files."
            )
    for destination in [args.out, report]:
        if destination.exists() and not args.force:
            raise InputError(f"Output exists: {destination}. Use --force to replace it.")
        if destination.exists() and not destination.is_file():
            raise InputError(f"Output is not a regular file: {destination}")
        if not destination.parent.is_dir():
            raise InputError(f"Output parent directory does not exist: {destination.parent}")


def _write_output(path: Path, content: bytes, *, force: bool):
    descriptor, staged_path = tempfile.mkstemp(prefix=".docx-repro-", dir=path.parent)
    staged = Path(staged_path)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if force:
            os.replace(staged, path)
        else:
            # Hard-link creation is atomic and refuses a destination that appeared during checking.
            os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def main(argv=None):
    args = parser().parse_args(argv)
    report_path = args.report or Path(str(args.out) + ".repro.json")
    try:
        if args.max_checks < args.confirmations * 3:
            raise InputError("max-checks must allow original, repacked and final confirmations.")
        _check_destinations(args, report_path)
        limits = Limits()
        if args.input.stat().st_size > limits.input_bytes:
            raise InputError("Input exceeds the compressed-size limit.")
        package = DocxPackage.load(args.input.read_bytes(), limits)
        if args.check_config is not None:
            config = CheckConfig.load(args.check_config)
        else:
            if not args.mammoth_missing_text.strip():
                raise InputError("The expected text must contain a non-whitespace character.")
            if importlib.util.find_spec("mammoth") is None:
                raise InputError(
                    'Install the optional checker with: pip install "docx-repro[mammoth]"'
                )
            config = CheckConfig(
                (
                    sys.executable,
                    "-m",
                    "docx_repro.mammoth_check",
                    "{file}",
                    "--expect-text-base64="
                    + base64.b64encode(args.mammoth_missing_text.encode("utf-8")).decode("ascii"),
                ),
                Path.cwd(),
            )
        with tempfile.TemporaryDirectory(prefix="docx-repro-") as temporary:
            runner = CheckRunner(
                config,
                Path(temporary) / "candidate.docx",
                timeout=args.timeout,
                max_checks=args.max_checks,
                max_seconds=args.max_seconds,
            )

            def progress(blocks, calls):
                if not args.quiet:
                    print(f"Kept {blocks} body blocks after {calls} checker runs", file=sys.stderr)

            result = reduce_package(
                package, runner, confirmations=args.confirmations, progress=progress
            )
        _check_destinations(args, report_path)
        _write_output(args.out, result.data, force=args.force)
        _write_output(
            report_path,
            (json.dumps(result.report, indent=2) + "\n").encode("utf-8"),
            force=args.force,
        )
        if not args.quiet:
            print(
                f"Saved {args.out}: {result.report['original_blocks']} -> "
                f"{result.report['reduced_blocks']} body blocks ({result.report['status']})."
            )
            print(f"Report: {report_path}")
        return 0
    except (ReproError, OSError, CheckLimit) as error:
        print(f"docx-repro: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("docx-repro: interrupted", file=sys.stderr)
        return 130
