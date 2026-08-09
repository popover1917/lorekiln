# Memory Anchor Contract

An anchor is an immutable logical range over the local dialogue journal, not an experience claim.

```yaml
anchor_id: ANCHOR-<UTC>-<REASON>-<RANDOM>
session_id: source Codex task
reason: manual | session_end | startup_recovery
start_offset: first unanchored journal byte
end_offset: last journaled complete-turn byte
source_transcript: local source path
content_path: logical anchor JSON containing journal segment IDs
content_sha256: integrity digest
message_count: normalized user and assistant messages
status: captured
distillation_status: pending | in_review | distilled | skipped
created_at: ISO-8601
```

Rules:

- Persist each completed turn incrementally at `Stop`; do not wait for `SessionEnd`.
- Advance the journal cursor only after the segment transaction commits.
- Let `SessionStart` recover a transcript tail only through the last complete final answer.
- Deduplicate by session and byte range.
- Preserve source pointers and hashes.
- Store normalized user/assistant messages; omit reasoning and raw tool output.
- Redact obvious credentials before writing content.
- Treat parse failures as skipped records, not permission to guess.
- A manual anchor excludes its own control turn.
- Only explicit intelligent-analysis work may change `distillation_status`; capture hooks never do.
- Resolve v4 logical anchors with `materialize-anchor`; continue to accept v3 anchors containing
  embedded `messages`.
