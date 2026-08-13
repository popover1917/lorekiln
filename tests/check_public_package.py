#!/usr/bin/env python3
"""Fail when the Lorekiln source tree contains local state or obvious secrets."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "lorekiln"
FORBIDDEN_NAMES = {".env"}
FORBIDDEN_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx"}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".ps1"}
PATTERNS = {
    "GitHub token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "user-specific Windows path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
    "user-specific Unix path": re.compile(r"/(?:Users|home)/[^/\s]+/"),
}


def main() -> int:
    failures: list[str] = []
    for path in PLUGIN.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden local-state file: {relative}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{label}: {relative}")
    if failures:
        print("Public package privacy check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Public package privacy check passed: {PLUGIN.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
