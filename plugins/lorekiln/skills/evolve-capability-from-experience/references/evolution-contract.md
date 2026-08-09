# Capability Evolution Contract

Every evolution run must preserve:

- target path and pre-change hash;
- approved and reusable experience IDs;
- unchanged baseline snapshot;
- eval prompts and assertions;
- candidate outputs and grading evidence;
- regression results;
- known limitations;
- rollback path.

The programmatic gate must also preserve:

- expected pre-change hashes recorded in the authorized report;
- a snapshot manifest created before the first target write;
- successful snapshot verification;
- an existing eval-evidence path before `implemented`.

If the target hashes differ from the authorized report, stop and obtain renewed authorization.
The database storing a rollback description is insufficient by itself; the snapshot payload and
manifest must exist and be verified.

## Mandatory human gate

Do not enter this workflow unless the user explicitly requests an edit and identifies the target.
Never infer modification intent from prior analysis, discussion, candidate approval, or routing.

Before the first write to a target capability, emit a change report containing the experience IDs,
evidence, exact target paths, intended diff scope, risks, tests, rollback, hook/global effects, and
expected token/context impact. Record the user's explicit authorization and bind it to those targets
and that scope. Approval of an experience record is not authorization to edit.

After implementation, require human review of the resulting diff and validation evidence before
recording that application as accepted. Keep the experience itself approved; acceptance is an
engineering-history event, not a new epistemic state. Any new target or material scope expansion
requires a new report and authorization.

Stop promotion when critical assertions regress, evidence is incomplete, or the change only succeeds on leaked or overfitted test context.
