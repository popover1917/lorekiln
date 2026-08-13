"""Isolated subprocess fixture for Lorekiln runtime tests."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "lorekiln"
RUNTIME = PLUGIN_ROOT / "scripts" / "memory_runtime.py"
STORE = PLUGIN_ROOT / "scripts" / "memory_store.py"


def transcript_record(role: str, text: str, *, phase: str | None = None) -> dict[str, Any]:
    payload_type = "user_message" if role == "user" else "agent_message"
    payload: dict[str, Any] = {"type": payload_type, "message": text}
    if phase is not None:
        payload["phase"] = phase
    return {
        "timestamp": "2026-08-13T00:00:00Z",
        "type": "event_msg",
        "payload": payload,
    }


class LorekilnSandbox:
    """Owns a temporary CODEX_HOME, PLUGIN_DATA, transcript, and store."""

    def __init__(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="lorekiln-test-")
        self.root = Path(self._temporary.name)
        self.codex_home = self.root / "codex home"
        self.plugin_data = self.root / "plugin data"
        self.transcript = self.root / "transcript.jsonl"
        self.store = self.root / "experience.sqlite3"
        self.target = self.root / "target.txt"
        self.snapshots = self.root / "rollback snapshots"
        self.codex_home.mkdir()
        self.plugin_data.mkdir()
        self.target.write_text("baseline\n", encoding="utf-8")

    def close(self) -> None:
        self._temporary.cleanup()

    def environment(self) -> dict[str, str]:
        value = os.environ.copy()
        value.update(
            {
                "CODEX_HOME": str(self.codex_home),
                "PLUGIN_DATA": str(self.plugin_data),
                "PYTHONUTF8": "1",
            }
        )
        return value

    def append_transcript(self, *records: dict[str, Any] | bytes) -> None:
        with self.transcript.open("ab") as handle:
            for record in records:
                raw = record if isinstance(record, bytes) else json.dumps(
                    record, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
                handle.write(raw + (b"" if raw.endswith(b"\n") else b"\n"))

    def event(self, session: str, turn: str, **values: Any) -> dict[str, Any]:
        return {
            "session_id": session,
            "turn_id": turn,
            "transcript_path": str(self.transcript),
            "cwd": str(self.root),
            **values,
        }

    def run(
        self,
        script: Path,
        *arguments: str,
        input_value: dict[str, Any] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            input=json.dumps(input_value, ensure_ascii=False) if input_value is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.environment(),
            timeout=10,
            check=False,
        )
        if check and result.returncode:
            raise AssertionError(
                f"command failed ({result.returncode}): {result.args}\n{result.stdout}\n{result.stderr}"
            )
        return result

    def hook(self, name: str, event: dict[str, Any]) -> dict[str, Any] | None:
        result = self.run(RUNTIME, "hook", name, input_value=event)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def runtime(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run(RUNTIME, *arguments, check=check)

    def store_command(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.run(STORE, "--db", str(self.store), *arguments, check=check)

    def rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.plugin_data / "memory.sqlite3")) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def store_rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.store)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def write_json(self, name: str, value: dict[str, Any]) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def install_trusted_hook_state(self) -> None:
        state_names = {
            "session_start": "a",
            "user_prompt_submit": "b",
            "stop": "c",
            "session_end": "d",
        }
        lines = []
        for normalized, suffix in state_names.items():
            key = f'lorekiln@lorekiln:hooks/hooks.json:{normalized}:{suffix}'
            lines.extend(
                [
                    f'[hooks.state."{key}"]',
                    "enabled = true",
                    f'trusted_hash = "fixture-{suffix}"',
                    "",
                ]
            )
        (self.codex_home / "config.toml").write_text("\n".join(lines), encoding="utf-8")
