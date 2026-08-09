#!/usr/bin/env python3
"""Local SQLite store for governed experience and capability evolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS experience (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    type TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL,
    promotion_target TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_request (
    id TEXT PRIMARY KEY,
    experience_ids_json TEXT NOT NULL,
    target_paths_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    tests_json TEXT NOT NULL,
    rollback TEXT NOT NULL,
    token_impact TEXT NOT NULL,
    explicit_user_request TEXT,
    status TEXT NOT NULL CHECK(status IN ('proposed', 'authorized', 'implemented', 'accepted', 'rejected')),
    authorization_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experience_application (
    experience_id TEXT NOT NULL,
    change_request_id TEXT NOT NULL,
    target_paths_json TEXT NOT NULL,
    application_status TEXT NOT NULL CHECK(application_status IN ('implemented', 'accepted', 'rolled_back', 'rejected')),
    outcome_note TEXT,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    implemented_at TEXT,
    accepted_at TEXT,
    rolled_back_at TEXT,
    rejected_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (experience_id, change_request_id),
    FOREIGN KEY (experience_id) REFERENCES experience(id),
    FOREIGN KEY (change_request_id) REFERENCES change_request(id)
);
CREATE INDEX IF NOT EXISTS experience_application_experience_idx
    ON experience_application(experience_id, updated_at);
CREATE INDEX IF NOT EXISTS experience_application_change_idx
    ON experience_application(change_request_id, updated_at);
CREATE TABLE IF NOT EXISTS experience_relation (
    source_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK(relation IN ('supports', 'contradicts', 'refines', 'supersedes', 'derived_from', 'applied_by')),
    target_id TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, relation, target_id),
    FOREIGN KEY (source_id) REFERENCES experience(id),
    FOREIGN KEY (target_id) REFERENCES experience(id)
);
CREATE INDEX IF NOT EXISTS experience_relation_source_idx
    ON experience_relation(source_id, relation);
CREATE INDEX IF NOT EXISTS experience_relation_target_idx
    ON experience_relation(target_id, relation);
CREATE VIRTUAL TABLE IF NOT EXISTS experience_fts USING fts5(
    id UNINDEXED, statement, domain, type, content='experience', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS experience_ai AFTER INSERT ON experience BEGIN
  INSERT INTO experience_fts(rowid, id, statement, domain, type)
  VALUES (new.rowid, new.id, new.statement, new.domain, new.type);
END;
CREATE TRIGGER IF NOT EXISTS experience_ad AFTER DELETE ON experience BEGIN
  INSERT INTO experience_fts(experience_fts, rowid, id, statement, domain, type)
  VALUES ('delete', old.rowid, old.id, old.statement, old.domain, old.type);
END;
CREATE TRIGGER IF NOT EXISTS experience_au AFTER UPDATE ON experience BEGIN
  INSERT INTO experience_fts(experience_fts, rowid, id, statement, domain, type)
  VALUES ('delete', old.rowid, old.id, old.statement, old.domain, old.type);
  INSERT INTO experience_fts(rowid, id, statement, domain, type)
  VALUES (new.rowid, new.id, new.statement, new.domain, new.type);
END;
"""


EXPERIENCE_MIGRATIONS = {
    "title": "TEXT",
    "domain_path": "TEXT",
    "project_scope": "TEXT",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "counterexamples_json": "TEXT NOT NULL DEFAULT '[]'",
    "source_anchor_ids_json": "TEXT NOT NULL DEFAULT '[]'",
    "supersedes_id": "TEXT",
    "related_experience_ids_json": "TEXT NOT NULL DEFAULT '[]'",
    "importance": "REAL NOT NULL DEFAULT 0.5",
    "freshness_policy": "TEXT",
    "last_verified_at": "TEXT",
    "usage_count": "INTEGER NOT NULL DEFAULT 0",
    "last_used_at": "TEXT",
}

CHANGE_MIGRATIONS = {
    "explicit_user_request": "TEXT",
    "expected_prechange_hashes_json": "TEXT",
    "snapshot_path": "TEXT",
    "prechange_hashes_json": "TEXT",
    "eval_path": "TEXT",
    "rollback_verified_at": "TEXT",
}

INDEX_COLUMNS = (
    "id", "title", "domain", "domain_path", "project_scope", "type",
    "statement", "confidence", "importance", "status", "updated_at",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate_columns(connection: sqlite3.Connection, table: str, migrations: dict[str, str]) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, declaration in migrations.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    # Existing V4 rows predate the FTS table. Populate the index before any
    # migration UPDATE fires the external-content delete/update triggers.
    connection.execute("INSERT INTO experience_fts(experience_fts) VALUES('rebuild')")
    migrate_columns(connection, "experience", EXPERIENCE_MIGRATIONS)
    migrate_columns(connection, "change_request", CHANGE_MIGRATIONS)
    connection.execute(
        """UPDATE experience
        SET domain_path = COALESCE(NULLIF(domain_path, ''), domain),
            title = COALESCE(NULLIF(title, ''), SUBSTR(statement, 1, 80))
        WHERE domain_path IS NULL OR domain_path = '' OR title IS NULL OR title = ''"""
    )
    connection.execute("INSERT INTO experience_fts(experience_fts) VALUES('rebuild')")
    migrate_application_history(connection)
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS experience_domain_path_idx
            ON experience(domain_path, status, updated_at);
        CREATE INDEX IF NOT EXISTS experience_project_scope_idx
            ON experience(project_scope, status, updated_at);
        """
    )
    connection.commit()
    return connection


def migrate_application_history(connection: sqlite3.Connection) -> None:
    """Normalize the legacy promoted state and reconstruct inspectable applications."""
    timestamp = now()
    rows = connection.execute(
        """SELECT id, experience_ids_json, target_paths_json, status, eval_path,
        authorization_note, created_at, updated_at
        FROM change_request WHERE status IN ('implemented', 'accepted')"""
    ).fetchall()
    for row in rows:
        application_status = row["status"]
        evidence = [row["eval_path"]] if row["eval_path"] else []
        for experience_id in json.loads(row["experience_ids_json"]):
            connection.execute(
                """INSERT INTO experience_application
                (experience_id, change_request_id, target_paths_json,
                 application_status, outcome_note, evidence_json,
                 implemented_at, accepted_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experience_id, change_request_id) DO NOTHING""",
                (
                    experience_id,
                    row["id"],
                    row["target_paths_json"],
                    application_status,
                    "Reconstructed from legacy change_request",
                    json_value(evidence, []),
                    row["updated_at"] if application_status == "implemented" else row["created_at"],
                    row["updated_at"] if application_status == "accepted" else None,
                    row["created_at"],
                    row["updated_at"],
                ),
            )
    connection.execute(
        "UPDATE experience SET status = 'approved', updated_at = ? WHERE status = 'promoted'",
        (timestamp,),
    )


def json_value(value: Any, default: Any) -> str:
    return json.dumps(default if value is None else value, ensure_ascii=False)


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in tuple(result):
        if key.endswith("_json") and result[key] is not None:
            try:
                result[key[:-5]] = json.loads(result.pop(key))
            except json.JSONDecodeError:
                pass
    return result


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    for row in rows:
        print(json.dumps(row_dict(row), ensure_ascii=False))


def normalize_domain_path(record: dict[str, Any]) -> str:
    value = str(record.get("domain_path") or record["domain"]).strip().strip("/")
    if not value:
        raise ValueError("domain_path must not be empty")
    if any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("domain_path contains an invalid segment")
    return value


def add_record(connection: sqlite3.Connection, input_path: Path) -> None:
    record = json.loads(input_path.read_text(encoding="utf-8"))
    required = ("id", "domain", "type", "statement", "evidence", "scope", "confidence")
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    confidence = float(record["confidence"])
    importance = float(record.get("importance", 0.5))
    if not 0 <= confidence <= 1 or not 0 <= importance <= 1:
        raise ValueError("confidence and importance must be between 0 and 1")
    timestamp = now()
    connection.execute(
        """INSERT INTO experience
        (id, domain, type, statement, evidence_json, scope_json, confidence,
         status, promotion_target, created_at, updated_at, title, domain_path,
         project_scope, tags_json, counterexamples_json, source_anchor_ids_json,
         supersedes_id, related_experience_ids_json, importance, freshness_policy,
         last_verified_at, usage_count, last_used_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record["id"], str(record["domain"]).strip(), record["type"],
            str(record["statement"]).strip(),
            json_value(record["evidence"], []), json_value(record["scope"], {}),
            confidence, record.get("status", "candidate"),
            record.get("promotion_target"), record.get("created_at", timestamp), timestamp,
            record.get("title"), normalize_domain_path(record),
            record.get("project_scope"), json_value(record.get("tags"), []),
            json_value(record.get("counterexamples"), []),
            json_value(record.get("source_anchor_ids"), []),
            record.get("supersedes_id"),
            json_value(record.get("related_experience_ids"), []),
            importance, record.get("freshness_policy"),
            record.get("last_verified_at"), int(record.get("usage_count", 0)),
            record.get("last_used_at"),
        ),
    )
    for related_id in record.get("related_experience_ids", []):
        connection.execute(
            """INSERT OR IGNORE INTO experience_relation
            (source_id, relation, target_id, note, created_at)
            VALUES (?, 'supports', ?, ?, ?)""",
            (record["id"], related_id, "Imported from related_experience_ids", timestamp),
        )
    connection.commit()


def set_status(connection: sqlite3.Connection, record_id: str, status: str) -> None:
    allowed = {"candidate", "approved", "rejected", "retired", "superseded"}
    if status not in allowed:
        raise ValueError(f"Unsupported status: {status}")
    row = connection.execute("SELECT status FROM experience WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown experience id: {record_id}")
    transitions = {
        "candidate": {"approved", "rejected"},
        "approved": {"retired", "superseded"},
        "rejected": set(),
        "retired": set(),
        "superseded": set(),
    }
    if status not in transitions[row["status"]]:
        raise ValueError(f"Unsupported status transition: {row['status']} -> {status}")
    connection.execute(
        "UPDATE experience SET status = ?, updated_at = ? WHERE id = ?",
        (status, now(), record_id),
    )
    connection.commit()


def build_filters(args: argparse.Namespace, alias: str = "experience") -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if getattr(args, "status", None):
        clauses.append(f"{alias}.status = ?")
        values.append(args.status)
    if getattr(args, "domain", None):
        clauses.append(f"({alias}.domain = ? OR {alias}.domain_path = ? OR {alias}.domain_path LIKE ?)")
        domain = args.domain.strip().strip("/")
        values.extend((domain, domain, f"{domain}/%"))
    if getattr(args, "project", None):
        clauses.append(f"{alias}.project_scope = ?")
        values.append(args.project)
    if getattr(args, "tag", None):
        clauses.append(
            f"""EXISTS (
                SELECT 1 FROM json_each({alias}.tags_json) WHERE json_each.value = ?
            )"""
        )
        values.append(args.tag)
    return clauses, values


def query_index(connection: sqlite3.Connection, args: argparse.Namespace) -> Iterable[sqlite3.Row]:
    clauses, values = build_filters(args)
    if getattr(args, "query", None):
        clauses.append(
            """experience.rowid IN (
                SELECT rowid FROM experience_fts WHERE experience_fts MATCH ?
            )"""
        )
        values.append(args.query)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(args.limit)
    return connection.execute(
        f"""SELECT {', '.join(INDEX_COLUMNS)}
        FROM experience {where}
        ORDER BY importance DESC, updated_at DESC LIMIT ?""",
        values,
    )


def list_domains(connection: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return connection.execute(
        """SELECT domain, COALESCE(domain_path, domain) AS domain_path,
        status, COUNT(*) AS count, MAX(updated_at) AS latest
        FROM experience
        GROUP BY domain, COALESCE(domain_path, domain), status
        ORDER BY domain_path, status"""
    )


def show_record(connection: sqlite3.Connection, record_id: str) -> None:
    row = connection.execute("SELECT * FROM experience WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown experience id: {record_id}")
    connection.execute(
        "UPDATE experience SET usage_count = usage_count + 1, last_used_at = ? WHERE id = ?",
        (now(), record_id),
    )
    connection.commit()
    print(json.dumps(row_dict(row), ensure_ascii=False))


def add_relation(connection: sqlite3.Connection, args: argparse.Namespace) -> None:
    timestamp = now()
    connection.execute(
        """INSERT INTO experience_relation
        (source_id, relation, target_id, note, created_at)
        VALUES (?, ?, ?, ?, ?)""",
        (args.source, args.relation, args.target, args.note, timestamp),
    )
    if args.relation == "supersedes":
        connection.execute(
            "UPDATE experience SET supersedes_id = ?, updated_at = ? WHERE id = ?",
            (args.target, timestamp, args.source),
        )
    connection.commit()


def related_records(connection: sqlite3.Connection, record_id: str, relation: str | None) -> Iterable[sqlite3.Row]:
    clauses = ["(r.source_id = ? OR r.target_id = ?)"]
    values: list[Any] = [record_id, record_id]
    if relation:
        clauses.append("r.relation = ?")
        values.append(relation)
    return connection.execute(
        f"""SELECT r.source_id, r.relation, r.target_id, r.note, r.created_at,
        CASE WHEN r.source_id = ? THEN target.title ELSE source.title END AS related_title,
        CASE WHEN r.source_id = ? THEN target.statement ELSE source.statement END AS related_statement
        FROM experience_relation r
        JOIN experience source ON source.id = r.source_id
        JOIN experience target ON target.id = r.target_id
        WHERE {' AND '.join(clauses)}
        ORDER BY r.created_at DESC""",
        [record_id, record_id, *values],
    )


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_target(path: Path) -> dict[str, str]:
    path = path.resolve()
    if path.is_file():
        return {str(path): hash_file(path)}
    if path.is_dir():
        return {
            str(item.resolve()): hash_file(item)
            for item in sorted(path.rglob("*"))
            if item.is_file()
        }
    raise ValueError(f"Target does not exist: {path}")


def hash_targets(paths: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in paths:
        result.update(hash_target(Path(raw)))
    return result


def ensure_safe_snapshot_root(path: Path) -> Path:
    resolved = path.resolve()
    forbidden = {Path(resolved.anchor), Path.home().resolve()}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"Unsafe snapshot root: {resolved}")
    return resolved


def hash_snapshot_copies(copies: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in copies:
        source = Path(item["source"])
        snapshot = Path(item["snapshot"])
        if snapshot.is_file():
            result[str(source)] = hash_file(snapshot)
        elif snapshot.is_dir():
            for copied in sorted(snapshot.rglob("*")):
                if copied.is_file():
                    result[str((source / copied.relative_to(snapshot)).resolve())] = hash_file(copied)
        else:
            raise ValueError(f"Snapshot payload is missing: {snapshot}")
    return result


def propose_change(connection: sqlite3.Connection, input_path: Path) -> None:
    request = json.loads(input_path.read_text(encoding="utf-8"))
    required = (
        "id", "experience_ids", "target_paths", "summary", "scope", "risks",
        "tests", "rollback", "token_impact", "explicit_user_request",
        "expected_prechange_hashes",
    )
    missing = [key for key in required if key not in request]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if not request["experience_ids"] or not request["target_paths"]:
        raise ValueError("experience_ids and target_paths must not be empty")
    explicit_request = str(request["explicit_user_request"]).strip()
    edit_verbs = r"(?:优化|修改|迭代|更新|修订|重构|实现|optimi[sz]e|modify|update|revise|iterate|refactor|implement)"
    target_words = r"(?:skill|技能|插件|plugin|agents\.md|hook|钩子|配置|工作流|capabilit|能力)"
    if not explicit_request or not (
        re.search(edit_verbs + r".*" + target_words, explicit_request, re.I)
        or re.search(target_words + r".*" + edit_verbs, explicit_request, re.I)
    ):
        raise ValueError("A quoted explicit user edit request naming the target capability is required")
    placeholders = ",".join("?" for _ in request["experience_ids"])
    rows = connection.execute(
        f"SELECT id, status FROM experience WHERE id IN ({placeholders})",
        tuple(request["experience_ids"]),
    ).fetchall()
    states = {row["id"]: row["status"] for row in rows}
    invalid = [item for item in request["experience_ids"] if states.get(item) != "approved"]
    if invalid:
        raise ValueError(f"Experience must be approved before proposing change: {', '.join(invalid)}")
    expected = request["expected_prechange_hashes"]
    if not isinstance(expected, dict) or not expected:
        raise ValueError("expected_prechange_hashes must be a non-empty object")
    timestamp = now()
    connection.execute(
        """INSERT INTO change_request
        (id, experience_ids_json, target_paths_json, summary, scope_json, risks_json,
         tests_json, rollback, token_impact, explicit_user_request,
         expected_prechange_hashes_json, status, authorization_note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', NULL, ?, ?)""",
        (
            request["id"], json_value(request["experience_ids"], []),
            json_value(request["target_paths"], []), request["summary"],
            json_value(request["scope"], {}), json_value(request["risks"], []),
            json_value(request["tests"], []), request["rollback"],
            request["token_impact"], explicit_request, json_value(expected, {}),
            timestamp, timestamp,
        ),
    )
    connection.commit()


def authorize_change(connection: sqlite3.Connection, request_id: str, note: str) -> None:
    if not note.strip():
        raise ValueError("Explicit authorization note is required")
    cursor = connection.execute(
        """UPDATE change_request SET status = 'authorized', authorization_note = ?, updated_at = ?
        WHERE id = ? AND status = 'proposed'""",
        (note, now(), request_id),
    )
    if cursor.rowcount != 1:
        raise ValueError("Change request must exist and be in proposed state")
    connection.commit()


def prepare_change(connection: sqlite3.Connection, request_id: str, snapshot_root: Path) -> None:
    row = connection.execute(
        """SELECT target_paths_json, expected_prechange_hashes_json, status
        FROM change_request WHERE id = ?""",
        (request_id,),
    ).fetchone()
    if row is None or row["status"] != "authorized":
        raise ValueError("Change request must be authorized before snapshot preparation")
    target_paths = json.loads(row["target_paths_json"])
    expected_hashes = json.loads(row["expected_prechange_hashes_json"] or "{}")
    actual_hashes = hash_targets(target_paths)
    if actual_hashes != expected_hashes:
        raise ValueError("Target content drifted after the change report; renewed authorization is required")
    root = ensure_safe_snapshot_root(snapshot_root)
    snapshot = root / request_id
    if snapshot.exists():
        raise ValueError(f"Snapshot already exists: {snapshot}")
    payload = snapshot / "payload"
    payload.mkdir(parents=True)
    copies: list[dict[str, str]] = []
    for index, raw in enumerate(target_paths, start=1):
        source = Path(raw).resolve()
        destination = payload / f"{index:03d}-{source.name}"
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copies.append({"source": str(source), "snapshot": str(destination)})
    manifest = {
        "change_request_id": request_id,
        "created_at": now(),
        "copies": copies,
        "prechange_hashes": actual_hashes,
        "snapshot_hashes": hash_snapshot_copies(copies),
    }
    manifest_path = snapshot / "manifest.json"
    temporary = snapshot / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    connection.execute(
        """UPDATE change_request
        SET snapshot_path = ?, prechange_hashes_json = ?, updated_at = ?
        WHERE id = ? AND status = 'authorized'""",
        (str(snapshot), json_value(actual_hashes, {}), now(), request_id),
    )
    connection.commit()
    print(json.dumps(manifest, ensure_ascii=False))


def verify_snapshot(connection: sqlite3.Connection, request_id: str) -> None:
    row = connection.execute(
        "SELECT snapshot_path, prechange_hashes_json FROM change_request WHERE id = ?",
        (request_id,),
    ).fetchone()
    if row is None or not row["snapshot_path"]:
        raise ValueError("No prepared snapshot exists")
    snapshot = Path(row["snapshot_path"])
    manifest_path = snapshot / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Snapshot manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["copies"]:
        if not Path(item["snapshot"]).exists():
            raise ValueError(f"Snapshot payload is missing: {item['snapshot']}")
    if manifest["prechange_hashes"] != json.loads(row["prechange_hashes_json"]):
        raise ValueError("Snapshot manifest does not match the database")
    if hash_snapshot_copies(manifest["copies"]) != manifest["prechange_hashes"]:
        raise ValueError("Snapshot payload hash verification failed")
    timestamp = now()
    connection.execute(
        "UPDATE change_request SET rollback_verified_at = ?, updated_at = ? WHERE id = ?",
        (timestamp, timestamp, request_id),
    )
    connection.commit()
    print(json.dumps({"change_request_id": request_id, "rollback_verified_at": timestamp}, ensure_ascii=False))


def advance_change(
    connection: sqlite3.Connection,
    request_id: str,
    status: str,
    note: str,
    eval_path: str | None,
) -> None:
    if not note.strip():
        raise ValueError("Human review note is required")
    expected = {"implemented": "authorized", "accepted": "implemented", "rejected": "proposed"}
    if status not in expected:
        raise ValueError(f"Unsupported change status: {status}")
    row = connection.execute(
        """SELECT experience_ids_json, status, snapshot_path,
        prechange_hashes_json, rollback_verified_at
        FROM change_request WHERE id = ?""",
        (request_id,),
    ).fetchone()
    if row is None or row["status"] != expected[status]:
        raise ValueError(f"Change request must be in {expected[status]} state before {status}")
    if status == "implemented":
        if not row["snapshot_path"] or not row["prechange_hashes_json"] or not row["rollback_verified_at"]:
            raise ValueError("A prepared and verified rollback snapshot is required before implemented")
        if not eval_path or not Path(eval_path).exists():
            raise ValueError("An existing eval evidence path is required before implemented")
    timestamp = now()
    connection.execute(
        """UPDATE change_request
        SET status = ?, authorization_note = ?, eval_path = COALESCE(?, eval_path), updated_at = ?
        WHERE id = ?""",
        (status, note, eval_path, timestamp, request_id),
    )
    if status in {"implemented", "accepted", "rejected"}:
        target_row = connection.execute(
            "SELECT target_paths_json FROM change_request WHERE id = ?", (request_id,)
        ).fetchone()
        evidence = [eval_path] if eval_path else []
        for experience_id in json.loads(row["experience_ids_json"]):
            upsert_application(
                connection,
                experience_id,
                request_id,
                target_row["target_paths_json"],
                status,
                note,
                evidence,
                timestamp,
            )
    connection.commit()


def upsert_application(
    connection: sqlite3.Connection,
    experience_id: str,
    change_request_id: str,
    target_paths_json: str,
    status: str,
    note: str,
    evidence: list[Any],
    timestamp: str | None = None,
) -> None:
    timestamp = timestamp or now()
    milestone_column = {
        "implemented": "implemented_at",
        "accepted": "accepted_at",
        "rolled_back": "rolled_back_at",
        "rejected": "rejected_at",
    }[status]
    connection.execute(
        f"""INSERT INTO experience_application
        (experience_id, change_request_id, target_paths_json,
         application_status, outcome_note, evidence_json, {milestone_column},
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(experience_id, change_request_id) DO UPDATE SET
          target_paths_json = excluded.target_paths_json,
          application_status = excluded.application_status,
          outcome_note = excluded.outcome_note,
          evidence_json = CASE
            WHEN excluded.evidence_json = '[]' THEN experience_application.evidence_json
            ELSE excluded.evidence_json
          END,
          {milestone_column} = excluded.{milestone_column},
          updated_at = excluded.updated_at""",
        (
            experience_id,
            change_request_id,
            target_paths_json,
            status,
            note,
            json_value(evidence, []),
            timestamp,
            timestamp,
            timestamp,
        ),
    )


def record_application_outcome(connection: sqlite3.Connection, args: argparse.Namespace) -> None:
    row = connection.execute(
        """SELECT experience_ids_json, target_paths_json FROM change_request
        WHERE id = ?""",
        (args.change_request_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown change request id: {args.change_request_id}")
    if args.experience_id not in json.loads(row["experience_ids_json"]):
        raise ValueError("Experience is not associated with the change request")
    evidence = [args.evidence] if args.evidence else []
    upsert_application(
        connection,
        args.experience_id,
        args.change_request_id,
        row["target_paths_json"],
        args.value,
        args.note,
        evidence,
    )
    connection.commit()


def list_applications(connection: sqlite3.Connection, args: argparse.Namespace) -> Iterable[sqlite3.Row]:
    clauses: list[str] = []
    values: list[Any] = []
    if args.experience_id:
        clauses.append("application.experience_id = ?")
        values.append(args.experience_id)
    if args.change_request_id:
        clauses.append("application.change_request_id = ?")
        values.append(args.change_request_id)
    if args.status:
        clauses.append("application.application_status = ?")
        values.append(args.status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(args.limit)
    return connection.execute(
        f"""SELECT application.*, experience.title, experience.domain_path,
        change_request.summary AS change_summary
        FROM experience_application application
        JOIN experience ON experience.id = application.experience_id
        JOIN change_request ON change_request.id = application.change_request_id
        {where} ORDER BY application.updated_at DESC LIMIT ?""",
        values,
    )


def add_filter_arguments(parser: argparse.ArgumentParser, include_query: bool = False) -> None:
    if include_query:
        parser.add_argument("query", nargs="?")
    parser.add_argument("--status")
    parser.add_argument("--domain")
    parser.add_argument("--project")
    parser.add_argument("--tag")
    parser.add_argument("--limit", type=int, default=50)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("input", type=Path)
    list_parser = subparsers.add_parser("list")
    add_filter_arguments(list_parser)
    index_parser = subparsers.add_parser("index")
    add_filter_arguments(index_parser, include_query=True)
    subparsers.add_parser("list-domains")
    timeline_parser = subparsers.add_parser("timeline")
    add_filter_arguments(timeline_parser)
    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("id")
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=20)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("id")
    status_parser.add_argument("value")
    relation_parser = subparsers.add_parser("add-relation")
    relation_parser.add_argument("source")
    relation_parser.add_argument(
        "relation",
        choices=("supports", "contradicts", "refines", "supersedes", "derived_from", "applied_by"),
    )
    relation_parser.add_argument("target")
    relation_parser.add_argument("--note")
    related_parser = subparsers.add_parser("related")
    related_parser.add_argument("id")
    related_parser.add_argument("--relation")
    conflicts_parser = subparsers.add_parser("conflicts")
    conflicts_parser.add_argument("id")

    propose_parser = subparsers.add_parser("propose-change")
    propose_parser.add_argument("input", type=Path)
    authorize_parser = subparsers.add_parser("authorize-change")
    authorize_parser.add_argument("id")
    authorize_parser.add_argument("--note", required=True)
    prepare_parser = subparsers.add_parser("prepare-change")
    prepare_parser.add_argument("id")
    prepare_parser.add_argument("--snapshot-root", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify-snapshot")
    verify_parser.add_argument("id")
    changes_parser = subparsers.add_parser("list-changes")
    changes_parser.add_argument("--status")
    advance_parser = subparsers.add_parser("advance-change")
    advance_parser.add_argument("id")
    advance_parser.add_argument("value", choices=("implemented", "accepted", "rejected"))
    advance_parser.add_argument("--note", required=True)
    advance_parser.add_argument("--eval-path")
    applications_parser = subparsers.add_parser("applications")
    applications_parser.add_argument("--experience-id")
    applications_parser.add_argument("--change-request-id")
    applications_parser.add_argument("--status")
    applications_parser.add_argument("--limit", type=int, default=50)
    outcome_parser = subparsers.add_parser("record-application-outcome")
    outcome_parser.add_argument("experience_id")
    outcome_parser.add_argument("change_request_id")
    outcome_parser.add_argument("value", choices=("implemented", "accepted", "rolled_back", "rejected"))
    outcome_parser.add_argument("--note", required=True)
    outcome_parser.add_argument("--evidence")

    args = parser.parse_args()
    with connect(args.db) as connection:
        if args.command == "add":
            add_record(connection, args.input)
        elif args.command == "list":
            print_rows(query_index(connection, args))
        elif args.command == "index":
            print_rows(query_index(connection, args))
        elif args.command == "list-domains":
            print_rows(list_domains(connection))
        elif args.command == "timeline":
            clauses, values = build_filters(args)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            values.append(args.limit)
            print_rows(connection.execute(
                f"""SELECT {', '.join(INDEX_COLUMNS)}
                FROM experience {where}
                ORDER BY updated_at ASC LIMIT ?""",
                values,
            ))
        elif args.command == "show":
            show_record(connection, args.id)
        elif args.command == "search":
            print_rows(connection.execute(
                """SELECT experience.* FROM experience_fts
                JOIN experience ON experience_fts.rowid = experience.rowid
                WHERE experience_fts MATCH ? ORDER BY bm25(experience_fts) LIMIT ?""",
                (args.query, args.limit),
            ))
        elif args.command == "status":
            set_status(connection, args.id, args.value)
        elif args.command == "add-relation":
            add_relation(connection, args)
        elif args.command == "related":
            print_rows(related_records(connection, args.id, args.relation))
        elif args.command == "conflicts":
            print_rows(related_records(connection, args.id, "contradicts"))
        elif args.command == "propose-change":
            propose_change(connection, args.input)
        elif args.command == "authorize-change":
            authorize_change(connection, args.id, args.note)
        elif args.command == "prepare-change":
            prepare_change(connection, args.id, args.snapshot_root)
        elif args.command == "verify-snapshot":
            verify_snapshot(connection, args.id)
        elif args.command == "list-changes":
            if args.status:
                rows = connection.execute(
                    "SELECT * FROM change_request WHERE status = ? ORDER BY updated_at DESC",
                    (args.status,),
                )
            else:
                rows = connection.execute("SELECT * FROM change_request ORDER BY updated_at DESC")
            print_rows(rows)
        elif args.command == "advance-change":
            advance_change(connection, args.id, args.value, args.note, args.eval_path)
        elif args.command == "applications":
            print_rows(list_applications(connection, args))
        elif args.command == "record-application-outcome":
            record_application_outcome(connection, args)


if __name__ == "__main__":
    main()
