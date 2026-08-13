# Lorekiln 0.2.1-rc.1 readiness

Date: 2026-08-13

Decision: **NO-GO for tagged release** until the remote CI matrix and clean
Codex install journeys are directly verified.

## Completed in source

- 18 isolated Windows tests pass on Python 3.12.13.
- Completed-turn journaling, recovery idempotence, malformed tails, UTF-8,
  missing transcripts, concurrent sessions, lock recovery, store migration,
  privacy redaction, and the authorization lifecycle have regression coverage.
- `doctor --support` is read-only, structured, and tested against missing and
  corrupt databases without exposing user-specific paths.
- The public package privacy check and the 1/10 MB benchmark pass.
- CI is configured for Ubuntu/Windows and Python 3.11/3.12.

## Required before GO

1. Verify all four GitHub Actions matrix jobs on the exact candidate commit.
2. From a clean clone and isolated Codex configuration on Windows, perform
   marketplace add, install/trust, first anchor, support doctor, uninstall, and
   data-removal verification.
3. Perform the same first-anchor journey on Ubuntu or another supported
   Unix-like environment.
4. Re-run the complete test and privacy suite from a fresh clone.
5. Obtain explicit owner approval before creating a candidate tag or Release.

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
