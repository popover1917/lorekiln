# Changelog

All notable public changes to Lorekiln are documented here.

## 0.2.1-rc.1 (candidate)

- Added strict completed-turn boundaries for normal writes and crash recovery.
- Added idempotence, malformed-input isolation, missing-transcript, concurrent-session,
  lock-contention, and path-with-spaces regression coverage.
- Added `doctor --support`, a read-only and privacy-safe support report.
- Added Windows and Ubuntu CI across Python 3.11 and 3.12.
- Added deterministic public-package privacy checks and a reproducible benchmark.
- This is source-level release-candidate preparation; no `v0.2.1-rc.1` tag or
  GitHub/Gitee release exists until the owner approves the release gate.

## 0.2.0

- Added deterministic local journaling across Codex lifecycle events.
- Added manual memory anchors over completed dialogue ranges.
- Added an explicit, evidence-backed experience distillation and review workflow.
- Added a durable, domain-organized experience pool with independent application history.
- Added separately authorized capability evolution with baselines, evals, rollback, and final acceptance.
- Published the first privacy-filtered standalone Lorekiln package.
