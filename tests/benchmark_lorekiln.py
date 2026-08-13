#!/usr/bin/env python3
"""Repeatable local timing probe; results are informational, never a CI threshold."""

from __future__ import annotations

import argparse
import json
import platform
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from lorekiln_support import LorekilnSandbox, transcript_record


def timed(callable_value):
    started = time.perf_counter()
    result = callable_value()
    return result, time.perf_counter() - started


def measure_transcript(size_mb: int) -> dict[str, float | int]:
    box = LorekilnSandbox()
    try:
        text = "x" * (64 * 1024)
        while not box.transcript.exists() or box.transcript.stat().st_size < size_mb * 1024 * 1024:
            box.append_transcript(
                transcript_record("user", text),
                transcript_record("assistant", text, phase="final_answer"),
            )
        box.hook("session-start", box.event(f"bench-{size_mb}", "start"))
        _, stop_seconds = timed(
            lambda: box.hook("stop", box.event(f"bench-{size_mb}", "stop"))
        )
        _, doctor_seconds = timed(lambda: box.runtime("doctor", "--support"))
        return {
            "requested_mb": size_mb,
            "actual_bytes": box.transcript.stat().st_size,
            "stop_seconds": round(stop_seconds, 4),
            "doctor_seconds": round(doctor_seconds, 4),
        }
    finally:
        box.close()


def measure_anchor_queries(count: int) -> dict[str, float | int]:
    box = LorekilnSandbox()
    try:
        box.append_transcript(
            transcript_record("user", "benchmark"),
            transcript_record("assistant", "answer", phase="final_answer"),
        )
        box.hook("session-start", box.event("bench-anchors", "start"))
        box.hook("stop", box.event("bench-anchors", "stop"))
        database = box.plugin_data / "memory.sqlite3"
        with closing(sqlite3.connect(database)) as connection:
            base = connection.execute("SELECT * FROM memory_anchor").fetchone()
            if base is None:
                box.hook("session-end", box.event("bench-anchors", "end"))
                base = connection.execute("SELECT * FROM memory_anchor").fetchone()
            columns = [row[1] for row in connection.execute("PRAGMA table_info(memory_anchor)")]
            template = dict(zip(columns, base))
            for index in range(1, count):
                value = dict(template)
                value["anchor_id"] = f"ANCHOR-BENCH-{index:06d}"
                value["session_id"] = f"bench-session-{index:06d}"
                value["start_offset"] = index * 2
                value["end_offset"] = index * 2 + 1
                connection.execute(
                    f"INSERT INTO memory_anchor ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    [value[name] for name in columns],
                )
            connection.commit()
        _, query_seconds = timed(lambda: box.runtime("list-anchors", "--limit", str(count)))
        return {"anchor_count": count, "list_seconds": round(query_seconds, 4)}
    finally:
        box.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1,10")
    parser.add_argument("--anchor-counts", default="100,1000")
    args = parser.parse_args()
    payload = {
        "method": "isolated subprocess fixture; wall-clock perf_counter; no network",
        "environment": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "hook_timeout_seconds": 3,
        "transcripts": [measure_transcript(int(value)) for value in args.sizes.split(",")],
        "anchor_queries": [measure_anchor_queries(int(value)) for value in args.anchor_counts.split(",")],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
