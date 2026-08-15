#!/usr/bin/env python3
"""Run the reproducible Lorekiln developer validation suite."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print(f"+ {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def validate_json() -> None:
    paths = (
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / "plugins" / "lorekiln" / ".codex-plugin" / "plugin.json",
        ROOT / "plugins" / "lorekiln" / "hooks" / "hooks.json",
    )
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"JSON valid: {path.relative_to(ROOT).as_posix()}")


def validate_python() -> None:
    paths = sorted((ROOT / "plugins").rglob("*.py")) + sorted((ROOT / "tests").rglob("*.py"))
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    print(f"Python AST valid: {len(paths)} files")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", action="store_true", help="run the reproducible benchmark")
    args = parser.parse_args()

    validate_json()
    validate_python()
    run(sys.executable, "tests/check_public_package.py")
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    if args.benchmark:
        run(sys.executable, "tests/benchmark_lorekiln.py")
    print("Lorekiln developer checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
