"""Execute explicit argv checkers with time, count, and mutation checks."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import CheckError, CheckLimit, InputError


@dataclass(frozen=True)
class CheckConfig:
    command: tuple[str, ...]
    cwd: Path

    @classmethod
    def load(cls, path: Path) -> CheckConfig:
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise InputError(f"Cannot read checker configuration: {error}") from error
        if not isinstance(config, dict) or set(config) - {"command", "cwd"}:
            raise InputError("Checker config supports only command and optional cwd.")
        command = config.get("command")
        if (
            not isinstance(command, list)
            or not command
            or any(
                not isinstance(argument, str) or not argument or "\x00" in argument
                for argument in command
            )
            or not any("{file}" in argument for argument in command[1:])
            or "{file}" in command[0]
        ):
            raise InputError("command must be an argv array with {file} in an argument.")
        cwd_value = config.get("cwd", ".")
        if not isinstance(cwd_value, str) or "\x00" in cwd_value:
            raise InputError("cwd must be a path string.")
        cwd = (path.resolve().parent / cwd_value).resolve()
        if not cwd.is_dir():
            raise InputError("Checker working directory does not exist.")
        executable = command[0]
        if ("/" in executable or "\\" in executable) and not Path(executable).is_absolute():
            command[0] = str((cwd / executable).resolve())
        if os.name == "nt" and Path(command[0]).suffix.lower() in {".bat", ".cmd"}:
            raise InputError("Use a direct executable for Windows checkers, such as python.exe.")
        return cls(tuple(command), cwd)


def _kill_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass  # Still terminate the checker below if tree cleanup is unavailable.
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


class CheckRunner:
    def __init__(self, config, candidate_path, *, timeout=10.0, max_checks=200, max_seconds=300.0):
        self.config = config
        self.path = candidate_path.resolve()
        self.timeout = timeout
        self.max_checks = max_checks
        self.deadline = time.monotonic() + max_seconds
        self.calls = 0
        self.elapsed_seconds = 0.0

    def ensure_budget(self, reserve=0, *, reserve_time=False):
        if self.calls + reserve >= self.max_checks:
            raise CheckLimit("check_limit")
        seconds = self.deadline - time.monotonic()
        if seconds <= (reserve * self.timeout if reserve_time else 0):
            raise CheckLimit("time_limit")

    def check(self, candidate: bytes) -> bool:
        self.ensure_budget()
        self.path.write_bytes(candidate)
        command = [argument.replace("{file}", str(self.path)) for argument in self.config.command]
        started = time.monotonic()
        remaining = self.deadline - started
        kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        self.calls += 1
        try:
            process = subprocess.Popen(
                command,
                cwd=self.config.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                **kwargs,
            )
        except OSError as error:
            raise CheckError(f"Cannot start checker: {error}") from error
        try:
            code = process.wait(timeout=min(self.timeout, remaining))
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            _kill_tree(process)
            if isinstance(error, KeyboardInterrupt):
                raise
            raise CheckError("Checker timed out; its result is inconclusive.") from error
        finally:
            self.elapsed_seconds += time.monotonic() - started
        try:
            unchanged = (
                self.path.stat().st_size == len(candidate) and self.path.read_bytes() == candidate
            )
        except OSError:
            unchanged = False
        if not unchanged:
            raise CheckError("Checker changed or removed its input; checkers must be read-only.")
        if code not in {0, 1}:
            raise CheckError(
                f"Checker exited with {code}; expected 0 (reproduces) or 1 (does not)."
            )
        return code == 0

    def confirm(self, candidate: bytes, repetitions: int):
        results = [self.check(candidate) for _ in range(repetitions)]
        if len(set(results)) > 1:
            raise CheckError("Checker gave inconsistent results for the same candidate.")
        return results[0]
