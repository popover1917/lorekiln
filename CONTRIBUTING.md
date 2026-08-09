# Contributing

Thank you for helping make governed agent memory more useful and inspectable.

## Before opening a pull request

1. Keep the change scoped to one product under `plugins/<name>`.
2. Do not include real conversations, local databases, credentials or machine-specific paths.
3. Explain the failure mode or user outcome the change addresses.
4. Add or update a reproducible test when behavior changes.
5. Run the public checks:

```bash
python -m unittest discover -s tests -v
python -m compileall -q plugins
```

For Lorekiln behavior changes, preserve the separation between mechanical capture, requested analysis, experience governance and explicitly authorized capability evolution.

## Pull request description

Include:

- what changed and why;
- the affected product and files;
- evidence or reproduction steps;
- tests executed and their results;
- privacy, token-cost and rollback impact.
