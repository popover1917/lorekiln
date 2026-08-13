# Security Policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature when available. Do not open a public issue containing credentials, private transcripts, local database contents or exploitable details.

Include the affected version, reproduction conditions, expected impact and the smallest safe proof of concept.

Before reporting, generate a privacy-safe diagnostic bundle:

```bash
python plugins/lorekiln/scripts/memory_runtime.py doctor --support > lorekiln-support.json
```

Review the JSON before attaching it. The command is read-only and intentionally
omits transcript content, credentials, raw configuration, and user-specific paths.

## Sensitive data

Lorekiln is designed to store dialogue and experience state locally. Treat generated SQLite files, materialized anchors, logs, tokens and Codex trust state as private. They must not be committed to this repository or attached to public issues.
