# Lorekiln repository instructions

This repository is the independent public Lorekiln product repository. Keep it
public-safe and standalone.

- Never commit transcripts, SQLite databases, anchor files, credentials,
  machine-specific paths, plugin trust state, or generated local memory.
- Preserve the separation between deterministic capture, requested semantic
  analysis, experience approval, capability-change authorization, and final
  acceptance.
- Run `python scripts/dev_check.py --benchmark` before committing behavior or
  release-readiness changes.
- On Windows with Ubuntu WSL2, also run
  `powershell -ExecutionPolicy Bypass -File scripts/dev-check-wsl.ps1 -Benchmark`.
- Check the current commit's GitHub Actions result with
  `python scripts/github_actions_status.py --wait-seconds 300`; this uses the
  public GitHub REST API and does not require browser access or `gh`.
- GitHub `main` is the source of truth. Gitee `main` is an exact mirror and is
  updated only when the owner explicitly requests it.
- Do not create tags, Releases, change repository visibility, rewrite shared
  history, or force-push without explicit owner approval.
