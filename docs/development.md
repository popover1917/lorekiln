# Development environment

Lorekiln uses the Python standard library and supports development on Windows
and Unix-like systems without a project-specific dependency installation.

## One-command validation

From the repository root:

```bash
python scripts/dev_check.py --benchmark
```

This validates JSON manifests, parses all Python files without generating
`__pycache__`, scans the public plugin package for local or sensitive state,
runs the complete test suite, and executes the reproducible benchmark.

## Ubuntu WSL2 on Windows

From PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev-check-wsl.ps1 -Benchmark
```

The wrapper resolves the current checkout through `wslpath` and runs the same
suite with Ubuntu's `python3`. It does not install packages or modify the WSL
distribution. Use `-Distribution <name>` when Ubuntu is not the desired distro.

## GitHub Actions without the web page or `gh`

```bash
python scripts/github_actions_status.py
python scripts/github_actions_status.py --wait-seconds 300
```

The command queries the public GitHub REST API for the local `HEAD`. Exit code
0 means the matching run completed successfully, 1 means it completed with a
non-success conclusion, and 2 means it is pending or not yet visible.

## VS Code

The repository includes tasks for the Windows suite, Ubuntu WSL2 suite, and
current GitHub Actions status. Run them through **Terminal: Run Task**. The
Python and WSL extensions are recommendations, not runtime dependencies.
