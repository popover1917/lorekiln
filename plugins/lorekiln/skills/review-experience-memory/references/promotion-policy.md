# Promotion Policy

Approve experience only when all mandatory checks pass:

- Evidence is identifiable and authorized.
- The claim is scoped and falsifiable.
- A counterexample or exclusion has been considered.
- No secrets or sensitive raw content are retained.
- The destination is the smallest durable surface that fits.
- A validation method exists.

Routing:

| Experience | Destination |
|---|---|
| Personal preference or background context | Codex Memory |
| Mandatory global behavior | Global `AGENTS.md` |
| Mandatory repository convention | Repository `AGENTS.md` |
| Repeatable workflow | Skill |
| Multi-skill workflow with hooks or MCP | Plugin |
| Unverified interpretation | Candidate store only |

## Two independent approvals

Keep these decisions separate:

1. **Experience approval** confirms that a lesson is evidence-backed and may be retained.
2. **Change authorization** permits a specified edit to a specified active target and begins only
   after the user explicitly asks to optimize, modify, update, revise, or iterate that target.

Experience approval never implies change authorization. Before editing an active Skill, plugin,
`AGENTS.md`, hook, config, memory control surface, or global behavior, present a change report that
states:

- experience IDs and evidence summary;
- exact target paths;
- proposed behavioral change and why it belongs there;
- planned file-level scope;
- risks, conflicts, tests, rollback path, and expected context/token impact;
- whether the change affects automatic hooks or cross-project behavior.

Stop after presenting the report. Proceed only after the user explicitly approves that target and
scope. Silence, discussion depth, approval of the experience itself, routing, or a general interest
in future improvement is neither an edit request nor approval. If the approved scope changes,
report again and obtain new approval.

## Durable experience pool

Approval moves a candidate into a long-lived, queryable pool. It does not start a timer for
promotion and does not require capability work in the same session. Organize approved records by
hierarchical domain and optional project scope. Preserve chronology, counterexamples, evidence
pointers, freshness, and explicit relations.

When discussing the pool, list a compact index for the requested domain first, inspect timelines,
conflicts, and related records for selected IDs second, and open full evidence only when necessary.
Retrieval and discussion remain read-only.

## Separate application history

Do not move an approved lesson to a `promoted` knowledge state after implementation. Keep the
lesson `approved` and record each engineering use independently:

- `implemented`: the authorized edit and eval evidence exist;
- `accepted`: the user adopted that particular result;
- `rolled_back`: the result was later reverted, while earlier milestones remain inspectable;
- `rejected`: the proposed application was declined.

The same approved experience may support multiple change requests. Acceptance increases the body
of evidence but does not automatically change confidence, importance, or future applicability.
