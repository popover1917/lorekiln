---
name: review-experience-memory
description: Audit, organize, query, and govern the durable experience pool for evidence quality, domains, duplication, conflicts, privacy, scope, freshness, and promotion readiness. Use when the user asks to review or discuss memories, approve lessons, inspect a domain's history, merge experience, remove stale guidance, resolve conflicting rules, or decide what should enter AGENTS.md, a Skill, or a plugin.
---

# Review Experience Memory

Treat memory as fallible generated state. Require evidence before approval and application.

## Review gates

For every candidate, decide:

1. Is its evidence inspectable and sufficient?
2. Is it recurring, high-impact, or merely incidental?
3. Is the statement more general than the evidence supports?
4. What tasks does it not apply to?
5. Does it conflict with a newer rule, official source, or user instruction?
6. Is it safe to retain?
7. Can promotion be validated with a concrete test?
8. Did collaborative analysis consider a competing interpretation or counterexample?

Read [references/promotion-policy.md](references/promotion-policy.md) before approving or routing candidates.

## Actions

- Approve: evidence and scope are adequate.
- Merge: combine duplicates while retaining every source pointer.
- Narrow: reduce scope or confidence.
- Reject: unsupported, harmful, secret-bearing, or irrelevant.
- Retire: once useful but now stale.
- Supersede: replace with a newer reviewed principle.

Approved experience is a durable pool, not a queue that must immediately modify a capability.
Retain it across days and sessions with domain, project, tag, chronology, relation, evidence, and
freshness metadata.

Keep epistemic state and engineering history separate. An accepted implementation is additional
evidence, not an automatic confidence increase. Query `applications --experience-id <id>` when the
user asks where an experience was used, whether it was accepted, or whether it was rolled back.

For historical discussion, retrieve in this order: compact domain/index results, selected
timeline/relations, then full evidence. Do not inject the pool automatically or load every record.

Never treat retrieval frequency as truth. Never modify Codex-generated files under `~/.codex/memories` as the primary control surface.
Never confuse an automatically captured memory anchor with an approved experience.

Approving an experience makes it reusable for one or more change proposals. It does not authorize any
edit to another Skill, plugin, `AGENTS.md`, hook, config, or global behavior. Before such an edit,
the user must explicitly request optimization, modification, iteration, or another concrete edit
of a named target. Then produce the change report required by the promotion policy and stop for
target-specific approval.
