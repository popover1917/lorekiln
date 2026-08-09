---
name: create-memory-anchor
description: Create or inspect a deterministic local checkpoint over the continuously persisted dialogue journal. Use when the user asks to save, checkpoint, archive, preserve, or persist completed conversation through the current point, establish or terminate a memory anchor, or mark everything since the previous anchor without analyzing experience.
---

# Create Memory Anchor

Keep capture mechanical and analysis separate.

## Workflow

1. Confirm that the request is to checkpoint dialogue, not merely summarize it.
2. Let the `UserPromptSubmit` hook freeze the journal boundary immediately before the control prompt.
3. Read the hook-provided anchor result. Do not reconstruct or extend the captured range manually.
4. Report the anchor ID, captured message count, scope, and `distillation_status`.
5. State explicitly that no experience analysis or capability change occurred.
6. If the hook reports no new content, report that result without creating a duplicate.

For status checks, use the plugin's real Codex data directory and run:

```powershell
python <plugin-root>/scripts/memory_runtime.py doctor
python <plugin-root>/scripts/memory_runtime.py status
python <plugin-root>/scripts/memory_runtime.py list-anchors --reason manual --limit 5
python <plugin-root>/scripts/memory_runtime.py materialize-anchor <anchor-id>
```

`doctor` must report `healthy: true` before claiming that lifecycle capture is active. Treat missing
hook-state entries, an absent database, or an audit event from an older runtime as a failed runtime
check. A cached Skill does not prove that its bundled hooks are trusted or running. On Windows, use
the bundled Codex Python path when `python` is unavailable.

Read [references/anchor-schema.md](references/anchor-schema.md) when auditing boundaries or stored
records.

## Boundaries

- Capture only complete dialogue before the anchor control prompt.
- Exclude the anchor command and its confirmation turn from future memory ranges.
- Treat `Stop` journal persistence as the primary capture path. `SessionEnd` is only a best-effort
  close marker; `SessionStart` repairs any completed tail missed by `Stop`.
- Never analyze, classify, promote, or inject captured content during anchoring.
- Never modify another Skill, plugin, `AGENTS.md`, hook, or config.
