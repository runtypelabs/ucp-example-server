"""Tiny progress reporter shared across validators."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from validator import Error


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    errors: list[Error] = field(default_factory=list)
    note: str | None = None


@dataclass
class Report:
    capability: str
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, errors: list[Error], *, note: str | None = None) -> CheckResult:
        result = CheckResult(name=name, passed=not errors, errors=errors, note=note)
        self.checks.append(result)
        self._print_line(result)
        return result

    def add_manual(self, name: str, passed: bool, *, note: str | None = None) -> CheckResult:
        result = CheckResult(name=name, passed=passed, errors=[], note=note)
        self.checks.append(result)
        self._print_line(result)
        return result

    def _print_line(self, result: CheckResult) -> None:
        if result.passed:
            marker = f"{GREEN}PASS{RESET}"
        else:
            marker = f"{RED}FAIL{RESET}"
        note = f" {DIM}- {result.note}{RESET}" if result.note else ""
        print(f"  [{marker}] {result.name}{note}")
        for err in result.errors[:8]:
            print(f"        {YELLOW}{err}{RESET}")
        if len(result.errors) > 8:
            print(f"        {DIM}... {len(result.errors) - 8} more errors{RESET}")

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        total = len(self.checks)
        failed = sum(1 for c in self.checks if not c.passed)
        if failed == 0:
            return f"{GREEN}{self.capability}: {total}/{total} passed{RESET}"
        return f"{RED}{self.capability}: {total - failed}/{total} passed — {failed} failed{RESET}"


def header(text: str) -> None:
    print(f"\n=== {text} ===", file=sys.stdout)
