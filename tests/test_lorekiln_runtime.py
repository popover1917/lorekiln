"""Offline lifecycle, storage, privacy, and authorization regression tests."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from lorekiln_support import LorekilnSandbox, transcript_record


class SandboxTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.box = LorekilnSandbox()

    def tearDown(self) -> None:
        root = self.box.root
        self.box.close()
        self.assertFalse(root.exists())


class IsolatedFixtureTests(SandboxTestCase):
    def test_fixture_uses_only_disposable_paths(self) -> None:
        self.box.append_transcript(
            transcript_record("user", "hello"),
            transcript_record("assistant", "world", phase="final_answer"),
        )
        self.box.hook("session-start", self.box.event("session-fixed", "turn-0"))
        self.box.hook("stop", self.box.event("session-fixed", "turn-1"))
        self.assertTrue((self.box.plugin_data / "memory.sqlite3").is_file())
        self.assertEqual(self.box.rows("SELECT COUNT(*) AS n FROM dialogue_segment")[0]["n"], 1)


class LifecycleTests(SandboxTestCase):
    def test_complete_user_journey_from_dialogue_to_authorized_verified_change(self) -> None:
        self.box.append_transcript(
            transcript_record("user", "请保留这段中文 🌱 e\u0301"),
            transcript_record("assistant", "已完成第一步。", phase="final_answer"),
        )
        self.box.hook("session-start", self.box.event("session-e2e", "turn-0"))
        self.box.hook("stop", self.box.event("session-e2e", "turn-1"))
        self.box.append_transcript(transcript_record("user", "Create a memory anchor now"))
        output = self.box.hook(
            "user-prompt-submit",
            self.box.event("session-e2e", "turn-anchor", prompt="Create a memory anchor now"),
        )
        self.assertIn("created memory anchor", output["hookSpecificOutput"]["additionalContext"])
        anchor = self.box.rows("SELECT * FROM memory_anchor")[0]
        materialized = json.loads(
            self.box.runtime("materialize-anchor", anchor["anchor_id"]).stdout
        )
        self.assertEqual([item["role"] for item in materialized["messages"]], ["user", "assistant"])
        self.assertEqual(
            [item["text"] for item in materialized["messages"]],
            ["请保留这段中文 🌱 e\u0301", "已完成第一步。"],
        )
        self.assertNotIn("Create a memory anchor", json.dumps(materialized, ensure_ascii=False))
        self.box.runtime("set-distillation", anchor["anchor_id"], "in_review")
        self.box.runtime("set-distillation", anchor["anchor_id"], "distilled")

        experience = self.box.write_json(
            "experience.json",
            {
                "id": "EXP-FIXTURE-001",
                "title": "Keep deterministic boundaries",
                "domain": "testing",
                "type": "practice",
                "statement": "Persist only complete answers.",
                "evidence": [{"source_type": "fixture", "source_id": anchor["anchor_id"]}],
                "scope": {"applies_to": ["runtime"]},
                "confidence": 0.9,
                "importance": 0.8,
                "source_anchor_ids": [anchor["anchor_id"]],
            },
        )
        self.box.store_command("add", str(experience))
        self.box.store_command("status", "EXP-FIXTURE-001", "approved")
        target_hash = hashlib.sha256(self.box.target.read_bytes()).hexdigest()
        request = self.box.write_json(
            "change.json",
            {
                "id": "CR-FIXTURE-001",
                "experience_ids": ["EXP-FIXTURE-001"],
                "target_paths": [str(self.box.target)],
                "summary": "Test authorization boundary",
                "scope": {"files": [str(self.box.target)]},
                "risks": ["fixture only"],
                "tests": ["this end-to-end test"],
                "rollback": str(self.box.snapshots),
                "token_impact": "none",
                "explicit_user_request": "Modify the named plugin target",
                "expected_prechange_hashes": {str(self.box.target.resolve()): target_hash},
            },
        )
        self.box.store_command("propose-change", str(request))
        denied = self.box.store_command(
            "prepare-change", "CR-FIXTURE-001", "--snapshot-root", str(self.box.snapshots), check=False
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(self.box.target.read_text(encoding="utf-8"), "baseline\n")
        self.assertEqual(self.box.store_rows("SELECT status FROM experience")[0]["status"], "approved")
        self.assertEqual(self.box.store_rows("SELECT status FROM change_request")[0]["status"], "proposed")

        self.box.store_command("authorize-change", "CR-FIXTURE-001", "--note", "Explicit fixture authorization")
        self.box.store_command(
            "prepare-change", "CR-FIXTURE-001", "--snapshot-root", str(self.box.snapshots)
        )
        self.box.store_command("verify-snapshot", "CR-FIXTURE-001")
        snapshot = self.box.store_rows(
            "SELECT status, snapshot_path, rollback_verified_at FROM change_request"
        )[0]
        self.assertEqual(snapshot["status"], "authorized")
        self.assertTrue(Path(snapshot["snapshot_path"]).is_dir())
        self.assertTrue(snapshot["rollback_verified_at"])
        illegal = self.box.store_command("status", "EXP-FIXTURE-001", "candidate", check=False)
        self.assertNotEqual(illegal.returncode, 0)

    def test_duplicate_hooks_are_idempotent_and_control_reply_stays_excluded(self) -> None:
        self.box.append_transcript(
            transcript_record("user", "first"),
            transcript_record("assistant", "answer", phase="final_answer"),
        )
        start = self.box.event("session-idem", "start")
        stop = self.box.event("session-idem", "turn-1")
        self.box.hook("session-start", start)
        self.box.hook("stop", stop)
        self.box.hook("stop", stop)
        self.box.append_transcript(transcript_record("user", "Create a memory anchor"))
        prompt = self.box.event("session-idem", "control", prompt="Create a memory anchor")
        self.box.hook("user-prompt-submit", prompt)
        self.box.hook("user-prompt-submit", prompt)
        self.box.append_transcript(
            transcript_record("assistant", "Anchor created.", phase="final_answer")
        )
        control_stop = self.box.event("session-idem", "control")
        self.box.hook("stop", control_stop)
        self.box.hook("stop", control_stop)
        self.box.append_transcript(
            transcript_record("user", "next"),
            transcript_record("assistant", "next answer", phase="final_answer"),
        )
        end = self.box.event("session-idem", "end", reason="done")
        self.box.hook("session-end", end)
        self.box.hook("session-end", end)
        self.assertEqual(self.box.rows("SELECT COUNT(*) AS n FROM dialogue_segment")[0]["n"], 2)
        self.assertEqual(self.box.rows("SELECT COUNT(*) AS n FROM memory_anchor")[0]["n"], 2)
        anchors = self.box.rows("SELECT * FROM memory_anchor ORDER BY start_offset")
        second = json.loads(self.box.runtime("materialize-anchor", anchors[1]["anchor_id"]).stdout)
        texts = [item["text"] for item in second["messages"]]
        self.assertEqual(texts, ["next", "next answer"])
        state = self.box.rows("SELECT * FROM session_state")[0]
        self.assertLessEqual(state["anchor_offset"], state["journal_offset"])
        self.assertLessEqual(state["journal_offset"], state["last_complete_offset"])

    def test_incomplete_corrupt_and_nonfinal_tail_is_recoverable_without_utf8_damage(self) -> None:
        first = transcript_record("user", "中文 🌏 e\u0301\nnext")
        final = transcript_record("assistant", "完整回答", phase="final_answer")
        self.box.append_transcript(first, b"{not-json}", final)
        self.box.hook("session-start", self.box.event("session-utf8", "start"))
        self.box.hook("stop", self.box.event("session-utf8", "turn-1"))
        stable_offset = self.box.rows("SELECT journal_offset FROM session_state")[0]["journal_offset"]
        self.box.append_transcript(
            transcript_record("assistant", "thinking", phase="commentary"),
            b'{"type":"event_msg","payload":',
        )
        self.box.hook("stop", self.box.event("session-utf8", "turn-2"))
        self.assertEqual(self.box.rows("SELECT journal_offset FROM session_state")[0]["journal_offset"], stable_offset)
        self.box.append_transcript(
            transcript_record("user", "补全后问题"),
            transcript_record("assistant", "补全后答案 ✅", phase="final_answer"),
        )
        self.box.hook("stop", self.box.event("session-utf8", "turn-3"))
        rows = self.box.rows("SELECT messages_json FROM dialogue_segment ORDER BY start_offset")
        all_messages = [message for row in rows for message in json.loads(row["messages_json"])]
        self.assertIn("中文 🌏 e\u0301\nnext", [item["text"] for item in all_messages])
        self.assertIn("补全后答案 ✅", [item["text"] for item in all_messages])

    def test_startup_recovery_is_repeatable_and_missing_transcript_is_isolated(self) -> None:
        self.box.append_transcript(
            transcript_record("user", "recover me"),
            transcript_record("assistant", "complete", phase="final_answer"),
        )
        self.box.hook("session-start", self.box.event("old-session", "old-start"))
        missing = self.box.root / "moved.jsonl"
        self.box.hook(
            "session-start",
            {
                "session_id": "missing-session",
                "turn_id": "missing-start",
                "transcript_path": str(missing),
                "cwd": str(self.box.root),
            },
        )
        self.box.hook("session-start", self.box.event("new-session", "new-start"))
        self.box.hook("session-start", self.box.event("newer-session", "newer-start"))
        anchors = self.box.rows("SELECT * FROM memory_anchor WHERE session_id = 'old-session'")
        self.assertEqual(len(anchors), 1)
        audit_lines = (self.box.plugin_data / "hook-events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("recover me", audit_lines)
        audit_events = [json.loads(line) for line in audit_lines.splitlines()]
        self.assertTrue(
            any("TRANSCRIPT_MISSING" in event.get("recovery_issue_codes", []) for event in audit_events)
        )


class ConcurrencyAndMigrationTests(SandboxTestCase):
    def test_sessions_remain_isolated_and_database_integrity_is_ok(self) -> None:
        transcript_a = self.box.transcript
        transcript_b = self.box.root / "other.jsonl"
        self.box.append_transcript(
            transcript_record("user", "A-user"),
            transcript_record("assistant", "A-answer", phase="final_answer"),
        )
        transcript_b.write_text(
            "\n".join(
                json.dumps(item)
                for item in (
                    transcript_record("user", "B-user"),
                    transcript_record("assistant", "B-answer", phase="final_answer"),
                )
            ) + "\n",
            encoding="utf-8",
        )
        event_a = self.box.event("session-A", "turn-A")
        event_b = self.box.event("session-B", "turn-B", transcript_path=str(transcript_b))
        self.box.hook("session-start", event_a)
        self.box.hook("session-start", event_b)
        self.box.hook("stop", event_b)
        self.box.hook("stop", event_a)
        rows = self.box.rows("SELECT session_id, messages_json FROM dialogue_segment ORDER BY session_id")
        self.assertEqual([row["session_id"] for row in rows], ["session-A", "session-B"])
        self.assertIn("A-user", rows[0]["messages_json"])
        self.assertNotIn("B-user", rows[0]["messages_json"])
        self.assertIn("B-user", rows[1]["messages_json"])
        self.assertEqual(next(iter(self.box.rows("PRAGMA integrity_check")[0].values())), "ok")

    def test_lock_contention_fails_visibly_then_next_hook_recovers(self) -> None:
        self.box.append_transcript(
            transcript_record("user", "locked"),
            transcript_record("assistant", "recoverable", phase="final_answer"),
        )
        self.box.hook("session-start", self.box.event("session-lock", "start"))
        database = self.box.plugin_data / "memory.sqlite3"
        lock = sqlite3.connect(database)
        lock.execute("BEGIN EXCLUSIVE")
        failed = self.box.run(
            Path(__file__).resolve().parents[1] / "plugins" / "lorekiln" / "scripts" / "memory_runtime.py",
            "hook", "stop", input_value=self.box.event("session-lock", "turn-1"), check=False,
        )
        lock.rollback()
        lock.close()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("locked", failed.stderr.lower())
        self.box.hook("stop", self.box.event("session-lock", "turn-1"))
        self.assertEqual(next(iter(self.box.rows("SELECT COUNT(*) FROM dialogue_segment")[0].values())), 1)
        self.assertEqual(next(iter(self.box.rows("PRAGMA integrity_check")[0].values())), "ok")

    def test_legacy_store_migration_is_idempotent_and_preserves_history(self) -> None:
        with closing(sqlite3.connect(self.box.store)) as connection:
            connection.executescript(
                """
                CREATE TABLE experience (
                  id TEXT PRIMARY KEY, domain TEXT NOT NULL, type TEXT NOT NULL,
                  statement TEXT NOT NULL, evidence_json TEXT NOT NULL, scope_json TEXT NOT NULL,
                  confidence REAL NOT NULL, status TEXT NOT NULL, promotion_target TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE change_request (
                  id TEXT PRIMARY KEY, experience_ids_json TEXT NOT NULL,
                  target_paths_json TEXT NOT NULL, summary TEXT NOT NULL,
                  scope_json TEXT NOT NULL, risks_json TEXT NOT NULL, tests_json TEXT NOT NULL,
                  rollback TEXT NOT NULL, token_impact TEXT NOT NULL,
                  status TEXT NOT NULL, authorization_note TEXT,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO experience VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("EXP-OLD", "legacy", "lesson", "old statement", "[]", "{}", 0.7,
                 "promoted", None, "2025-01-01", "2025-01-02"),
            )
            connection.execute(
                "INSERT INTO change_request VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("CR-OLD", '[\"EXP-OLD\"]', '[\"fixture\"]', "old change", "{}", "[]", "[]",
                 "backup", "none", "accepted", "reviewed", "2025-01-01", "2025-01-02"),
            )
            connection.commit()
        self.box.store_command("list")
        self.box.store_command("list")
        record = self.box.store_rows("SELECT status, domain_path, title FROM experience")[0]
        self.assertEqual(record["status"], "approved")
        self.assertEqual(record["domain_path"], "legacy")
        self.assertEqual(next(iter(self.box.store_rows("SELECT COUNT(*) FROM experience_application")[0].values())), 1)
        self.assertTrue(next(iter(self.box.store_rows("SELECT COUNT(*) FROM experience_fts WHERE experience_fts MATCH 'old'")[0].values())))
        self.assertEqual(self.box.store_rows("PRAGMA foreign_key_check"), [])
        invalid = self.box.store_command("status", "EXP-OLD", "candidate", check=False)
        self.assertNotEqual(invalid.returncode, 0)


class PrivacyAndDoctorTests(SandboxTestCase):
    def test_claimed_secret_formats_are_redacted_without_keyword_false_positives(self) -> None:
        samples = [
            "sk-fixtureABCDEFGHIJKLMN",
            "Bearer abcdefghijklmnop",
            "api_key=fixture-secret-value",
            "TOKEN: fixture-token-value",
            "Password = fixture-password",
            "secret: fixture-secret",
            "```python\ntoken='fixture-code-token'\n```",
        ]
        natural = "Token budgets and secret gardens are ordinary phrases."
        self.box.append_transcript(
            transcript_record("user", "\n".join(samples)),
            transcript_record("assistant", natural, phase="final_answer"),
        )
        self.box.hook("session-start", self.box.event("session-secret", "start"))
        self.box.hook("stop", self.box.event("session-secret", "turn"))
        stored = self.box.rows("SELECT messages_json FROM dialogue_segment")[0]["messages_json"]
        for secret in ("sk-fixture", "abcdefghijklmnop", "fixture-secret-value", "fixture-token-value", "fixture-password", "fixture-secret", "fixture-code-token"):
            self.assertNotIn(secret, stored)
        self.assertIn(natural, stored)
        self.assertEqual(stored.count("[REDACTED"), 7)

    def test_support_doctor_is_read_only_structured_and_issue_safe(self) -> None:
        secret = "sk-fixture-do-not-leak-123456"
        dialogue = "private fixture dialogue must not leak"
        self.box.append_transcript(
            transcript_record("user", secret),
            transcript_record("assistant", dialogue, phase="final_answer"),
        )
        self.box.install_trusted_hook_state()
        self.box.hook("session-start", self.box.event("session-doctor", "start"))
        self.box.hook("stop", self.box.event("session-doctor", "turn"))
        before = (self.box.plugin_data / "memory.sqlite3").stat().st_mtime_ns
        report_text = self.box.runtime("doctor", "--support").stdout
        after = (self.box.plugin_data / "memory.sqlite3").stat().st_mtime_ns
        report = json.loads(report_text)
        self.assertEqual(before, after)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["reason_codes"], [])
        self.assertEqual(report["report_format_version"], 1)
        self.assertEqual(report["sqlite_user_version"], 4)
        self.assertNotIn(secret, report_text)
        self.assertNotIn(dialogue, report_text)
        self.assertNotIn(str(self.box.root), report_text)
        self.assertNotIn("data_dir", report)

    def test_support_doctor_does_not_create_database_and_reports_partial_failure(self) -> None:
        empty_data = self.box.plugin_data
        self.assertFalse((empty_data / "memory.sqlite3").exists())
        report = json.loads(self.box.runtime("doctor", "--support").stdout)
        self.assertFalse(report["healthy"])
        self.assertIn("DATABASE_MISSING", report["reason_codes"])
        self.assertIn("HOOK_STATE_INCOMPLETE", report["reason_codes"])
        self.assertFalse((empty_data / "memory.sqlite3").exists())

    def test_support_doctor_handles_corrupt_database_without_leaking_path(self) -> None:
        database = self.box.plugin_data / "memory.sqlite3"
        database.write_bytes(b"not a sqlite database; private fixture body")
        report_text = self.box.runtime("doctor", "--support").stdout
        report = json.loads(report_text)
        self.assertFalse(report["healthy"])
        self.assertIn("DATABASE_UNREADABLE_OR_INVALID", report["reason_codes"])
        self.assertNotIn(str(self.box.root), report_text)
        self.assertNotIn("private fixture body", report_text)


if __name__ == "__main__":
    unittest.main()
