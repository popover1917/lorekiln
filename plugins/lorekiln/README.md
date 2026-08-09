# Lorekiln plugin reference

Lorekiln helps Codex learn from real work without treating every conversation as permanent truth or silently rewriting its own behavior.

## Responsibility boundaries

```text
completed dialogue
  -> deterministic local journal
  -> user-requested experience distillation
  -> governed experience pool
  -> separately authorized capability change
```

Most agent memory products optimize for recall: capture more, retrieve more, inject more. Lorekiln instead optimizes for provenance and control.

- Raw dialogue evidence remains inspectable.
- Mechanical capture runs without model calls.
- Analysis happens only when requested.
- Candidate lessons can be approved, narrowed, rejected, retired, or superseded.
- Approved experience does not automatically edit a Skill or plugin.
- Capability changes require a named target, a change report, tests, rollback material, explicit authorization, and final acceptance.

## Components

| Component | Responsibility |
|---|---|
| `create-memory-anchor` | Create deterministic checkpoints over completed dialogue. |
| `distill-dialogue-experience` | Turn explicitly selected evidence into reviewable experience candidates. |
| `review-experience-memory` | Query, approve, narrow, merge, reject, and retire experience records. |
| `evolve-capability-from-experience` | Apply approved experience to a named capability behind authorization, eval, and rollback gates. |
| Lifecycle hooks | Persist completed turns locally and repair missed tails after abnormal exits. |
| SQLite scripts | Store evidence, experience state, relations, change requests, and application history. |

## Lifecycle model

| Event | Behavior |
|---|---|
| `Stop` | Primary incremental journal write for a completed turn. |
| `SessionEnd` | Best-effort close marker; not the sole persistence mechanism. |
| `SessionStart` | Repairs completed dialogue missed before an abnormal exit. |
| `UserPromptSubmit` | Detects an explicit manual-anchor request and freezes the boundary before the control prompt. |

Mechanical capture never triggers analysis. Analysis never authorizes a capability edit. Approval of an experience never implies acceptance of an implementation.

## Local verification

From `plugins/lorekiln`:

```bash
python scripts/memory_runtime.py doctor
python scripts/memory_runtime.py status
python scripts/memory_runtime.py list-anchors --reason manual --limit 5
```

On Windows, the hook manifest uses `hooks/run_memory_hook.ps1` so runtime discovery does not depend on one shell's Python command resolution.

## Privacy model

- Dialogue journals, SQLite databases, and runtime state stay in the local Codex plugin data directory.
- The public source tree contains no real conversations, access tokens, trust state, or user databases.
- Experience retrieval is progressive: inspect the index first, then expand selected relations or evidence.
- Generated plugin data must never be committed when developing or reporting an issue.

Lorekiln is early-access software. Reproducible issues and focused pull requests are welcome; keep private transcripts out of reports.
