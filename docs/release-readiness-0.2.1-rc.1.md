# Lorekiln 0.2.1-rc.1 readiness

Date: 2026-08-13

Decision: **CONDITIONAL GO for a bounded Early Access community rollout from
`main`; NO-GO for a new tag, Release, or stable-version claim** until the clean
Codex install journeys are directly verified.

Candidate implementation commit: `8d8a1b0bc0f4167e8c4b3fdab2788ab38002327d`

## Completed in source

- 18 isolated Windows tests pass on Python 3.12.13.
- Completed-turn journaling, recovery idempotence, malformed tails, UTF-8,
  missing transcripts, concurrent sessions, lock recovery, store migration,
  privacy redaction, and the authorization lifecycle have regression coverage.
- `doctor --support` is read-only, structured, and tested against missing and
  corrupt databases without exposing user-specific paths.
- The public package privacy check and the 1/10 MB benchmark pass.
- CI is configured for Ubuntu/Windows and Python 3.11/3.12.
- [GitHub Actions quality run #4](https://github.com/popover1917/lorekiln/actions/runs/31673514235)
  completed successfully for Ubuntu 3.11, Ubuntu 3.12, Windows 3.11, and
  Windows 3.12 on the candidate implementation commit.
- A real Windows uninstall/data-retention check confirmed that the four
  Lorekiln Skills and active plugin cache were removed while the historical
  store remained intact. The database contained 63 unique anchors and the
  materialized anchor directory contained the same 63 records: 62
  `captured/pending` and one `captured/in_review`.
- The complete 18-test public suite and benchmark pass locally under Ubuntu
  WSL2, Linux kernel `6.6.87.2-microsoft-standard-WSL2`, and Python 3.12.3.
  This is direct Unix-like source/runtime evidence, but it does not substitute
  for a clean Codex marketplace install and Hook-trust journey on Linux.
- GitHub Actions run
  [31679481459](https://github.com/popover1917/lorekiln/actions/runs/31679481459)
  completed successfully for public commit `d565a44584e905cb233e203340e81a3f17e9de96`.

## Early Access rollout boundary

The public `main` branch is suitable for a small, explicitly scoped community
or design-partner rollout when every invitation states that Lorekiln is Early
Access software. This approval covers source discovery, installation trials,
technical feedback, and product-positioning work. It does not claim a stable
release, complete clean-install coverage, or verified Codex installation on
Unix-like hosts.

Reports must use `doctor --support` and must not include transcripts, SQLite
databases, anchor files, credentials, or full private paths.

## Required before stable/tagged GO

1. From a clean clone and isolated Codex configuration on Windows, perform
   marketplace add, install/trust, first anchor, support doctor, uninstall, and
   data-removal verification.
2. Perform the same first-anchor journey on Ubuntu or another supported
   Unix-like environment.
3. Re-run the complete test and privacy suite from a fresh clone.
4. Obtain explicit owner approval before creating a candidate tag or Release.

## Local evidence

```text
AST parse passed: 8 files
Public package privacy check passed: plugins/lorekiln
Ran 18 tests in 8.368s — OK
1 MB Stop: 0.1592s; 10 MB Stop: 0.4734s
1000-anchor list query: 0.0878s
```

The timing values are observations on one Windows 11 AMD64 machine, not global
performance guarantees.
