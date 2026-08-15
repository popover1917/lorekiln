#!/usr/bin/env python3
"""Check Lorekiln GitHub Actions without requiring a browser or GitHub CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.parse
import urllib.request


def current_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def fetch_runs(repository: str, branch: str) -> list[dict[str, object]]:
    query = urllib.parse.urlencode({"branch": branch, "per_page": 20})
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/runs?{query}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "lorekiln-dev-check"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)["workflow_runs"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="popover1917/lorekiln")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--sha", default=None, help="commit SHA; defaults to local HEAD")
    parser.add_argument("--wait-seconds", type=int, default=0, help="bounded wait for completion")
    args = parser.parse_args()
    target = args.sha or current_sha()
    deadline = time.monotonic() + max(args.wait_seconds, 0)

    while True:
        run = next((item for item in fetch_runs(args.repository, args.branch) if item["head_sha"] == target), None)
        if run is not None:
            result = {
                "head_sha": run["head_sha"],
                "status": run["status"],
                "conclusion": run["conclusion"],
                "url": run["html_url"],
            }
            print(json.dumps(result, indent=2))
            if run["status"] == "completed":
                return 0 if run["conclusion"] == "success" else 1
        elif args.wait_seconds == 0:
            print(json.dumps({"head_sha": target, "status": "not-found"}, indent=2))
            return 2

        if time.monotonic() >= deadline:
            return 2
        time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
