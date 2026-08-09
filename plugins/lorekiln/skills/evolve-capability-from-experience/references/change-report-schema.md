# Change Report Schema

Use this structure before requesting authorization:

```yaml
change_request_id: CR-YYYYMMDD-NNN
experience_ids: [EXP-YYYYMMDD-NNN]
evidence_summary: concise inspectable summary
target_paths: [exact/path/to/target]
expected_prechange_hashes:
  exact/path/to/file: sha256
behavioral_change: what will change and why it belongs in this target
explicit_user_request: exact user instruction containing an edit verb and named target
scope:
  files: [planned/file]
  excludes: [explicitly untouched areas]
risks: []
tests: []
rollback: exact snapshot or restoration path
token_impact: expected context or runtime cost
automatic_or_global_effects: none-or-details
authorization_status: proposed
```

After presenting the report, stop. Store explicit authorization separately; never prefill it or
infer it from experience approval.

After authorization, run `prepare-change` with a safe snapshot root and then `verify-snapshot`
before writing. Mark the change and its application `implemented` only with an existing eval path.
Record the application as `accepted` only after the user explicitly accepts the result; leave the
associated experience `approved` and unchanged. Use `record-application-outcome` for a later
rollback or explicit application rejection.
