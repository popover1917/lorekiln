---
name: evolve-capability-from-experience
description: Modify a named Codex Skill, plugin, AGENTS.md workflow, or reusable capability from approved experience using baselines, evals, regression tests, and rollback records. Trigger only when the user explicitly asks to optimize, modify, update, revise, or iterate a specific capability. Do not trigger from capture, analysis, discussion, review, approval, routing, or general interest in future improvement.
---

# Evolve Capability from Experience

Use only approved experience. Do not let candidates silently rewrite active capabilities.

## Explicit trigger gate

Require both:

1. an explicit edit verb such as optimize, modify, update, revise, iterate, or implement; and
2. an identifiable target Skill, plugin, `AGENTS.md`, hook, config, or reusable capability.

If either is absent, do not start capability evolution. Never infer edit intent from how much
discussion occurred. Discussion depth is not a trigger or authorization signal.

## Workflow

1. Confirm the explicit edit request, named target, and approved experience IDs.
2. Inspect the target read-only and record its path and content hash.
3. Define the expected improvement, file-level scope, risks, tests, rollback, and token/context impact.
4. Present an explicit change report and stop. Do not edit any target capability yet.
5. Continue only after the user explicitly authorizes the named target and scope.
6. Use the deterministic store command to compare the reported target hashes, create a snapshot,
   and verify its rollback manifest before editing. Refuse to continue on content drift.
7. Create normal, edge, and near-miss tests before editing.
8. Make the smallest authorized, generalizable change.
9. Validate structure and scripts, then compare against the frozen baseline.
10. Add a regression case for every confirmed fix and report any scope drift for renewed approval.
11. Record an existing eval-evidence path before marking the request `implemented`.
12. Present the completed diff and evidence for human review before promotion.
13. Preserve rollback material and record that application as `accepted` only after the user
    accepts the result. Keep the source experience `approved` and reusable.

Never batch unrelated targets under one approval. Authorization to update this plugin does not
authorize changes to another plugin or Skill. A request to analyze, distill, review, recommend, or
route experience is read-only with respect to target capabilities.

Before any completion claim, run fresh verification that directly proves the requested behavior.
Treat failed or contradictory evidence as a reason to report the actual state, not to soften the
claim.

The change-request `implemented` state means the authorized edit and tests exist; application
`accepted` means the user has reviewed and adopted that result. Never infer acceptance from
silence. Record later rollback without deleting the prior acceptance milestone. Do not change
experience confidence, importance, or approval merely because one application was accepted.

When editing a Skill, use the built-in `skill-creator`. For rigorous testing, use `skill-creator-evals`. When packaging multiple capabilities, use `plugin-creator`.

Read [references/evolution-contract.md](references/evolution-contract.md) before material changes.
Use [references/change-report-schema.md](references/change-report-schema.md) for the mandatory pre-edit report.
