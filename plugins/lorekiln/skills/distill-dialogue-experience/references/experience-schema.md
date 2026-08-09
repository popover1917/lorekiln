# Experience Candidate Schema

Use this minimum structure:

```yaml
id: EXP-YYYYMMDD-NNN
domain: skill-development
domain_path: skill-development/evaluation
project_scope: optional-project-or-null
type: failure-pattern
title: Short index title
statement: A concise reusable lesson
evidence:
  - source_type: transcript
    source_id: thread-or-observation-id
    pointer: path-or-reference
scope:
  applies_to: [complex-skills]
  excludes: [disposable-prototypes]
tags: [evals, regression]
confidence: 0.80
importance: 0.75
status: candidate
counterexamples: []
source_anchor_ids: [ANCHOR-YYYYMMDD-NNN]
related_experience_ids: []
freshness_policy: review-after-180-days
promotion_target: skill-name-or-AGENTS.md
created_at: ISO-8601
last_verified_at: null
supersedes: []
```

Allowed statuses:

- `candidate`
- `approved`
- `rejected`
- `retired`
- `superseded`

Keep the original evidence pointer immutable. Corrections should create a new record or mark the old record as superseded.

Engineering use is not an experience status. Store each use independently in
`experience_application`, keyed by the experience and change request, with an application status
of `implemented`, `accepted`, `rolled_back`, or `rejected`. Preserve milestone timestamps and
evidence so later rollback does not erase a prior acceptance event.

Use slash-delimited hierarchical domains such as
`mathematical-modeling/paper-writing/visualization` or
`lorekiln/token-efficiency`.

An approved record remains reusable in the durable experience pool until it is retired or
superseded. Approval and later application do not change its confidence automatically. Use
relations `supports`, `contradicts`,
`refines`, `supersedes`, `derived_from`, and `applied_by` to retain history without overwriting
earlier evidence.
