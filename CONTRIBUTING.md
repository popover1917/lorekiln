# Contributing

Thank you for helping make governed agent memory more useful and inspectable.

## Before opening a pull request

1. Keep the change scoped to one product under `plugins/<name>`.
2. Do not include real conversations, local databases, credentials or machine-specific paths.
3. Explain the failure mode or user outcome the change addresses.
4. Add or update a reproducible test when behavior changes.
5. Run the public checks:

```bash
python scripts/dev_check.py --benchmark
```

On Windows with Ubuntu WSL2, also run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-check-wsl.ps1 -Benchmark
```

See [development environment](docs/development.md) for VS Code tasks and the
browser-independent GitHub Actions status command.

For Lorekiln behavior changes, preserve the separation between mechanical capture, requested analysis, experience governance and explicitly authorized capability evolution.

## Pull request description

Include:

- what changed and why;
- the affected product and files;
- evidence or reproduction steps;
- tests executed and their results;
- privacy, token-cost and rollback impact.
