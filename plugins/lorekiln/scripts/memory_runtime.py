#!/usr/bin/env python3
"""Deterministic, local-only dialogue capture for Lorekiln."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tomllib
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANCHOR_PATTERNS = [
    re.compile(r"沉淀.*截止.*当前.*对话"),
    re.compile(r"建立.*记忆锚点"),
    re.compile(r"(?:建立|创建|终止).*锚点"),
    re.compile(r"保存.*未.*入库.*对话"),
    re.compile(r"保存.*尚未沉淀.*对话"),
    re.compile(r"把上次锚点之后.*入库"),
    re.compile(r"截止到这里保存记忆"),
    re.compile(r"\b(?:create|save|set)\b.*\bmemory anchor\b", re.I),
]

PLUGIN_INSTANCE = "lorekiln@lorekiln"
PLUGIN_DATA_FOLDER = "lorekiln"
RUNTIME_VERSION = "turn-journal-v4"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    transcript_path TEXT,
    cwd TEXT,
    anchor_offset INTEGER NOT NULL DEFAULT 0,
    journal_offset INTEGER NOT NULL DEFAULT 0,
    last_complete_offset INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS dialogue_segment (
    segment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    messages_json TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, start_offset, end_offset)
);
CREATE TABLE IF NOT EXISTS turn_event (
    session_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    event TEXT NOT NULL,
    transcript_path TEXT,
    byte_offset INTEGER NOT NULL,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, turn_id, event)
);
CREATE TABLE IF NOT EXISTS memory_anchor (
    anchor_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    transcript_path TEXT NOT NULL,
    content_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    message_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'captured',
    distillation_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    UNIQUE(session_id, start_offset, end_offset)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def data_dir(create: bool = True) -> Path:
    configured = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    target = Path(configured) if configured else codex_home() / "plugins" / "data" / PLUGIN_DATA_FOLDER
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(data_dir() / "memory.sqlite3", timeout=2.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=2000")
    connection.executescript(SCHEMA)
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(session_state)").fetchall()
    }
    if "journal_offset" not in columns:
        connection.execute(
            "ALTER TABLE session_state ADD COLUMN journal_offset INTEGER NOT NULL DEFAULT 0"
        )
        connection.execute(
            "UPDATE session_state SET journal_offset = anchor_offset"
        )
        connection.commit()
    return connection


def append_audit(event: dict[str, Any]) -> None:
    event = {
        "runtime_version": RUNTIME_VERSION,
        **event,
        "at": event.get("at", utc_now()),
    }
    with (data_dir() / "hook-events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def file_size(path_value: str | None) -> int:
    if not path_value:
        return 0
    path = Path(path_value)
    try:
        return path.stat().st_size
    except OSError:
        return 0


def upsert_session(connection: sqlite3.Connection, event: dict[str, Any]) -> sqlite3.Row:
    session_id = str(event.get("session_id") or "")
    if not session_id:
        raise ValueError("Hook input is missing session_id")
    transcript_path = str(event.get("transcript_path") or "")
    cwd = str(event.get("cwd") or "")
    connection.execute(
        """INSERT INTO session_state
        (session_id, transcript_path, cwd, last_seen_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
          transcript_path = CASE WHEN excluded.transcript_path != '' THEN excluded.transcript_path ELSE session_state.transcript_path END,
          cwd = CASE WHEN excluded.cwd != '' THEN excluded.cwd ELSE session_state.cwd END,
          last_seen_at = excluded.last_seen_at,
          state = 'open'""",
        (session_id, transcript_path, cwd, utc_now()),
    )
    connection.commit()
    return connection.execute(
        "SELECT * FROM session_state WHERE session_id = ?", (session_id,)
    ).fetchone()


def is_anchor_prompt(prompt: str) -> bool:
    compact = " ".join(prompt.strip().split())
    return any(pattern.search(compact) for pattern in ANCHOR_PATTERNS)


def redact(text: str) -> str:
    patterns = [
        (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_OPENAI_KEY]"),
        (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"), "Bearer [REDACTED]"),
        (
            re.compile(r"(?i)\b(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]{6,})"),
            lambda match: f"{match.group(1)}=[REDACTED]",
        ),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text


def extract_messages(path_value: str, start: int, end: int) -> list[dict[str, Any]]:
    path = Path(path_value)
    if not path.exists() or end <= start:
        return []
    messages: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        handle.seek(start)
        raw = handle.read(end - start)
    for raw_line in raw.splitlines():
        try:
            record = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if record.get("type") != "event_msg":
            continue
        payload = record.get("payload") or {}
        payload_type = payload.get("type")
        if payload_type == "user_message":
            text = payload.get("message")
            role = "user"
        elif payload_type == "agent_message":
            text = payload.get("message")
            role = "assistant"
        else:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        messages.append(
            {
                "timestamp": record.get("timestamp"),
                "role": role,
                "text": redact(text.strip()),
                "phase": payload.get("phase"),
            }
        )
    return messages


def discover_complete_offset(path_value: str, start: int, end: int) -> int:
    """Return the last transcript byte ending a completed visible assistant answer."""
    path = Path(path_value)
    if not path.exists() or end <= start:
        return start
    complete = start
    with path.open("rb") as handle:
        handle.seek(start)
        while handle.tell() < end:
            raw_line = handle.readline(end - handle.tell())
            line_end = handle.tell()
            try:
                record = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if record.get("type") != "event_msg":
                continue
            payload = record.get("payload") or {}
            if (
                payload.get("type") == "agent_message"
                and payload.get("phase") in (None, "final_answer")
            ):
                complete = line_end
    return complete


def sync_journal(
    connection: sqlite3.Connection,
    session_id: str,
    requested_end: int,
) -> dict[str, Any]:
    """Persist only the completed transcript suffix not already in the local journal."""
    state = connection.execute(
        "SELECT * FROM session_state WHERE session_id = ?", (session_id,)
    ).fetchone()
    if state is None or not state["transcript_path"]:
        return {"status": "skipped", "reason": "missing_session_or_transcript"}
    start = int(state["journal_offset"])
    end = min(int(requested_end), file_size(state["transcript_path"]))
    if end <= start:
        return {"status": "no_new_content", "session_id": session_id, "offset": start}
    messages = extract_messages(state["transcript_path"], start, end)
    serialized_messages = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(serialized_messages.encode("utf-8")).hexdigest()
    segment_id = f"SEG-{hashlib.sha256(f'{session_id}:{start}:{end}'.encode()).hexdigest()[:20]}"
    connection.execute(
        """INSERT OR IGNORE INTO dialogue_segment
        (segment_id, session_id, start_offset, end_offset, messages_json,
         content_sha256, message_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            segment_id,
            session_id,
            start,
            end,
            serialized_messages,
            digest,
            len(messages),
            utc_now(),
        ),
    )
    connection.execute(
        """UPDATE session_state
        SET journal_offset = MAX(journal_offset, ?),
            last_complete_offset = MAX(last_complete_offset, ?),
            last_seen_at = ?
        WHERE session_id = ?""",
        (end, end, utc_now(), session_id),
    )
    connection.commit()
    return {
        "status": "journaled",
        "segment_id": segment_id,
        "session_id": session_id,
        "message_count": len(messages),
        "start_offset": start,
        "end_offset": end,
        "content_sha256": digest,
    }


def make_anchor_id(reason: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"ANCHOR-{stamp}-{reason.upper()}-{uuid.uuid4().hex[:8]}"


def commit_anchor(
    connection: sqlite3.Connection,
    session_id: str,
    reason: str,
) -> dict[str, Any]:
    state = connection.execute(
        "SELECT * FROM session_state WHERE session_id = ?", (session_id,)
    ).fetchone()
    if state is None or not state["transcript_path"]:
        return {"status": "skipped", "reason": "missing_session_or_transcript"}
    start = int(state["anchor_offset"])
    end = int(state["journal_offset"])
    if end <= start:
        return {"status": "no_new_content", "session_id": session_id, "offset": start}
    existing = connection.execute(
        """SELECT * FROM memory_anchor
        WHERE session_id = ? AND start_offset = ? AND end_offset = ?""",
        (session_id, start, end),
    ).fetchone()
    if existing:
        return {"status": "existing", "anchor_id": existing["anchor_id"]}
    segments = connection.execute(
        """SELECT segment_id, messages_json, message_count
        FROM dialogue_segment
        WHERE session_id = ? AND start_offset >= ? AND end_offset <= ?
        ORDER BY start_offset""",
        (session_id, start, end),
    ).fetchall()
    message_count = sum(int(segment["message_count"]) for segment in segments)
    if message_count == 0:
        return {"status": "skipped", "reason": "no_dialogue_messages", "start": start, "end": end}
    anchor_id = make_anchor_id(reason)
    payload = {
        "anchor_id": anchor_id,
        "session_id": session_id,
        "reason": reason,
        "start_offset": start,
        "end_offset": end,
        "source_transcript": state["transcript_path"],
        "captured_at": utc_now(),
        "storage": "journal_segments",
        "segment_ids": [segment["segment_id"] for segment in segments],
        "message_count": message_count,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    anchor_dir = data_dir() / "anchors"
    anchor_dir.mkdir(parents=True, exist_ok=True)
    content_path = anchor_dir / f"{anchor_id}.json"
    temp_path = anchor_dir / f".{anchor_id}.tmp"
    temp_path.write_bytes(serialized)
    temp_path.replace(content_path)
    digest = hashlib.sha256(serialized).hexdigest()
    connection.execute(
        """INSERT INTO memory_anchor
        (anchor_id, session_id, reason, start_offset, end_offset, transcript_path,
         content_path, content_sha256, message_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            anchor_id,
            session_id,
            reason,
            start,
            end,
            state["transcript_path"],
            str(content_path),
            digest,
            message_count,
            utc_now(),
        ),
    )
    connection.execute(
        "UPDATE session_state SET anchor_offset = ? WHERE session_id = ?",
        (end, session_id),
    )
    connection.commit()
    return {
        "status": "captured",
        "anchor_id": anchor_id,
        "session_id": session_id,
        "message_count": message_count,
        "start_offset": start,
        "end_offset": end,
        "content_sha256": digest,
    }


def recover_uncommitted(connection: sqlite3.Connection, exclude_session: str | None = None) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT * FROM session_state
        WHERE (? IS NULL OR session_id != ?)""",
        (exclude_session, exclude_session),
    ).fetchall()
    results = []
    for row in rows:
        transcript_end = file_size(row["transcript_path"])
        recovered_end = discover_complete_offset(
            row["transcript_path"], int(row["journal_offset"]), transcript_end
        )
        if recovered_end > int(row["journal_offset"]):
            sync_journal(connection, row["session_id"], recovered_end)
        refreshed = connection.execute(
            "SELECT * FROM session_state WHERE session_id = ?", (row["session_id"],)
        ).fetchone()
        if int(refreshed["journal_offset"]) <= int(refreshed["anchor_offset"]):
            continue
        result = commit_anchor(connection, row["session_id"], "startup_recovery")
        if result.get("status") == "captured":
            results.append(result)
    return results


def record_turn_event(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    kind: str,
    offset: int,
    content: str | None = None,
) -> None:
    connection.execute(
        """INSERT OR IGNORE INTO turn_event
        (session_id, turn_id, event, transcript_path, byte_offset, content_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            str(event.get("session_id") or ""),
            str(event.get("turn_id") or "unknown"),
            kind,
            str(event.get("transcript_path") or ""),
            offset,
            hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None,
            utc_now(),
        ),
    )
    connection.commit()


def handle_session_start(connection: sqlite3.Connection, event: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(event.get("session_id") or "")
    recovered = recover_uncommitted(connection)
    upsert_session(connection, event)
    append_audit(
        {
            "event": "SessionStart",
            "session_id": session_id,
            "source": event.get("source"),
            "recovered_anchor_count": len(recovered),
            "context_injected": False,
        }
    )
    return None


def handle_user_prompt(connection: sqlite3.Connection, event: dict[str, Any]) -> dict[str, Any] | None:
    state = upsert_session(connection, event)
    prompt = str(event.get("prompt") or "")
    offset = file_size(state["transcript_path"])
    record_turn_event(connection, event, "prompt_submitted", offset, prompt)
    if not is_anchor_prompt(prompt):
        return None
    record_turn_event(connection, event, "manual_anchor_control", offset, prompt)
    sync_journal(connection, state["session_id"], int(state["last_complete_offset"]))
    result = commit_anchor(connection, state["session_id"], "manual")
    append_audit(
        {
            "event": "ManualAnchor",
            "session_id": state["session_id"],
            "turn_id": event.get("turn_id"),
            **result,
        }
    )
    if result.get("status") == "captured":
        message = (
            f"Lorekiln created memory anchor {result['anchor_id']} with "
            f"{result['message_count']} dialogue messages. This is raw mechanical memory only; "
            "no experience analysis or capability change was performed."
        )
    else:
        message = (
            "Lorekiln found no new completed dialogue before this control prompt. "
            "No experience analysis or capability change was performed."
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": message,
        }
    }


def handle_stop(connection: sqlite3.Connection, event: dict[str, Any]) -> dict[str, Any]:
    state = upsert_session(connection, event)
    offset = file_size(state["transcript_path"])
    connection.execute(
        """UPDATE session_state
        SET last_complete_offset = MAX(last_complete_offset, ?), last_seen_at = ?
        WHERE session_id = ?""",
        (offset, utc_now(), state["session_id"]),
    )
    record_turn_event(
        connection,
        event,
        "turn_completed",
        offset,
        str(event.get("last_assistant_message") or ""),
    )
    control = connection.execute(
        """SELECT 1 FROM turn_event
        WHERE session_id = ? AND turn_id = ? AND event = 'manual_anchor_control'""",
        (state["session_id"], str(event.get("turn_id") or "unknown")),
    ).fetchone()
    if control:
        connection.execute(
            """UPDATE session_state
            SET anchor_offset = MAX(anchor_offset, ?),
                journal_offset = MAX(journal_offset, ?)
            WHERE session_id = ?""",
            (offset, offset, state["session_id"]),
        )
        connection.commit()
        journal_result = {"status": "control_turn_excluded", "end_offset": offset}
    else:
        journal_result = sync_journal(
            connection,
            state["session_id"],
            offset,
        )
    append_audit(
        {
            "event": "Stop",
            "session_id": state["session_id"],
            "turn_id": event.get("turn_id"),
            "complete_offset": offset,
            "control_turn_skipped": bool(control),
            "journal_result": journal_result,
        }
    )
    return {}


def handle_session_end(connection: sqlite3.Connection, event: dict[str, Any]) -> None:
    state = upsert_session(connection, event)
    transcript_end = file_size(state["transcript_path"])
    recovered_end = discover_complete_offset(
        state["transcript_path"], int(state["journal_offset"]), transcript_end
    )
    sync_result = sync_journal(connection, state["session_id"], recovered_end)
    result = commit_anchor(connection, state["session_id"], "session_end")
    connection.execute(
        "UPDATE session_state SET state = 'closed', last_seen_at = ? WHERE session_id = ?",
        (utc_now(), state["session_id"]),
    )
    connection.commit()
    append_audit(
        {
            "event": "SessionEnd",
            "session_id": state["session_id"],
            "reason": event.get("reason"),
            "queued": result.get("status") == "captured",
            "sync_result": sync_result,
            "anchor_result": result,
        }
    )


def run_hook(hook_name: str) -> None:
    event = json.load(sys.stdin)
    with closing(connect()) as connection:
        if hook_name == "session-start":
            output = handle_session_start(connection, event)
        elif hook_name == "user-prompt-submit":
            output = handle_user_prompt(connection, event)
        elif hook_name == "stop":
            output = handle_stop(connection, event)
        elif hook_name == "session-end":
            handle_session_end(connection, event)
            output = None
        else:
            raise ValueError(f"Unknown hook: {hook_name}")
    if output is not None:
        print(json.dumps(output, ensure_ascii=False))


def list_anchors(limit: int, reason: str | None) -> None:
    with closing(connect()) as connection:
        if reason:
            rows = connection.execute(
                "SELECT * FROM memory_anchor WHERE reason = ? ORDER BY created_at DESC LIMIT ?",
                (reason, limit),
            )
        else:
            rows = connection.execute(
                "SELECT * FROM memory_anchor ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        for row in rows:
            print(json.dumps(dict(row), ensure_ascii=False))


def materialize_anchor(anchor_id: str) -> None:
    """Resolve a logical v4 anchor, while remaining compatible with v3 anchor files."""
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT * FROM memory_anchor WHERE anchor_id = ?", (anchor_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown anchor id: {anchor_id}")
        payload = json.loads(Path(row["content_path"]).read_text(encoding="utf-8"))
        if isinstance(payload.get("messages"), list):
            messages = payload["messages"]
        else:
            messages = []
            segment_ids = payload.get("segment_ids") or []
            for segment_id in segment_ids:
                segment = connection.execute(
                    "SELECT messages_json FROM dialogue_segment WHERE segment_id = ?",
                    (segment_id,),
                ).fetchone()
                if segment:
                    messages.extend(json.loads(segment["messages_json"]))
        resolved = {
            "anchor_id": anchor_id,
            "session_id": row["session_id"],
            "reason": row["reason"],
            "start_offset": row["start_offset"],
            "end_offset": row["end_offset"],
            "message_count": len(messages),
            "distillation_status": row["distillation_status"],
            "messages": messages,
        }
        print(json.dumps(resolved, ensure_ascii=False, indent=2))


def show_status() -> None:
    target = data_dir(create=False)
    database = target / "memory.sqlite3"
    counts: dict[str, Any] = {
        "runtime_version": RUNTIME_VERSION,
        "data_dir": str(target),
        "database_exists": database.exists(),
        "sessions": 0,
        "anchors": 0,
        "pending_distillation": 0,
        "uncommitted_sessions": 0,
        "unsynced_sessions": 0,
        "journal_segments": 0,
        "journal_messages": 0,
    }
    if not database.exists():
        print(json.dumps(counts, ensure_ascii=False))
        return
    with closing(connect()) as connection:
        counts = {
            **counts,
            "sessions": connection.execute("SELECT COUNT(*) FROM session_state").fetchone()[0],
            "anchors": connection.execute("SELECT COUNT(*) FROM memory_anchor").fetchone()[0],
            "pending_distillation": connection.execute(
                "SELECT COUNT(*) FROM memory_anchor WHERE distillation_status = 'pending'"
            ).fetchone()[0],
            "uncommitted_sessions": connection.execute(
                "SELECT COUNT(*) FROM session_state WHERE journal_offset > anchor_offset"
            ).fetchone()[0],
            "unsynced_sessions": connection.execute(
                "SELECT COUNT(*) FROM session_state WHERE last_complete_offset > journal_offset"
            ).fetchone()[0],
            "journal_segments": connection.execute(
                "SELECT COUNT(*) FROM dialogue_segment"
            ).fetchone()[0],
            "journal_messages": connection.execute(
                "SELECT COALESCE(SUM(message_count), 0) FROM dialogue_segment"
            ).fetchone()[0],
        }
    print(json.dumps(counts, ensure_ascii=False))


def read_last_audit_event(target: Path) -> dict[str, Any] | None:
    audit_path = target / "hook-events.jsonl"
    if not audit_path.exists():
        return None
    last: dict[str, Any] | None = None
    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                last = value
    return last


def hook_state_summary() -> dict[str, Any]:
    config_path = codex_home() / "config.toml"
    expected = {
        "SessionStart": "session_start",
        "UserPromptSubmit": "user_prompt_submit",
        "Stop": "stop",
        "SessionEnd": "session_end",
    }
    result: dict[str, Any] = {"config_path": str(config_path), "events": {}}
    if not config_path.exists():
        result["config_exists"] = False
        return result
    result["config_exists"] = True
    try:
        with config_path.open("rb") as handle:
            parsed = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result["config_error"] = str(exc)
        return result
    states = parsed.get("hooks", {}).get("state", {})
    for display_name, normalized in expected.items():
        prefix = f"{PLUGIN_INSTANCE}:hooks/hooks.json:{normalized}:"
        matches = [key for key in states if key.startswith(prefix)]
        entries = [states[key] for key in matches]
        result["events"][display_name] = {
            "state_entries": matches,
            "enabled": any(entry.get("enabled", True) for entry in entries),
            "trusted_hash_recorded": any(bool(entry.get("trusted_hash")) for entry in entries),
        }
    result["state_complete"] = all(
        event["state_entries"] and event["enabled"] and event["trusted_hash_recorded"]
        for event in result["events"].values()
    )
    result["note"] = (
        "A recorded trust hash may belong to an older hook definition. "
        "Codex is authoritative and skips changed definitions until the user trusts them."
    )
    return result


def doctor() -> None:
    target = data_dir(create=False)
    database = target / "memory.sqlite3"
    last_audit = read_last_audit_event(target)
    hook_state = hook_state_summary()
    report = {
        "runtime_version": RUNTIME_VERSION,
        "data_dir": str(target),
        "database_exists": database.exists(),
        "last_audit_event": last_audit,
        "hook_state": hook_state,
        "healthy": bool(
            database.exists()
            and last_audit
            and last_audit.get("runtime_version") == RUNTIME_VERSION
            and hook_state.get("state_complete")
        ),
    }
    print(json.dumps(report, ensure_ascii=False))


def set_distillation(anchor_id: str, status: str) -> None:
    allowed = {"pending", "in_review", "distilled", "skipped"}
    if status not in allowed:
        raise ValueError(f"Unsupported distillation status: {status}")
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT distillation_status FROM memory_anchor WHERE anchor_id = ?", (anchor_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown anchor id: {anchor_id}")
        transitions = {
            "pending": {"in_review", "skipped"},
            "in_review": {"pending", "distilled", "skipped"},
            "distilled": set(),
            "skipped": {"pending"},
        }
        if status not in transitions[row["distillation_status"]]:
            raise ValueError(
                f"Unsupported distillation transition: {row['distillation_status']} -> {status}"
            )
        connection.execute(
            "UPDATE memory_anchor SET distillation_status = ? WHERE anchor_id = ?",
            (status, anchor_id),
        )
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    hook_parser = subparsers.add_parser("hook")
    hook_parser.add_argument(
        "name", choices=("session-start", "user-prompt-submit", "stop", "session-end")
    )
    list_parser = subparsers.add_parser("list-anchors")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--reason")
    materialize_parser = subparsers.add_parser("materialize-anchor")
    materialize_parser.add_argument("anchor_id")
    distill_parser = subparsers.add_parser("set-distillation")
    distill_parser.add_argument("anchor_id")
    distill_parser.add_argument("status", choices=("pending", "in_review", "distilled", "skipped"))
    subparsers.add_parser("status")
    subparsers.add_parser("doctor")
    args = parser.parse_args()
    if args.command == "hook":
        run_hook(args.name)
    elif args.command == "list-anchors":
        list_anchors(args.limit, args.reason)
    elif args.command == "status":
        show_status()
    elif args.command == "materialize-anchor":
        materialize_anchor(args.anchor_id)
    elif args.command == "set-distillation":
        set_distillation(args.anchor_id, args.status)
    elif args.command == "doctor":
        doctor()


if __name__ == "__main__":
    main()
