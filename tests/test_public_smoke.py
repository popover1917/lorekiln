from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "lorekiln"


class PublicPackageSmokeTests(unittest.TestCase):
    def test_manifest_and_hooks_are_valid_json(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "lorekiln")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(set(hooks["hooks"]), {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"})

    def test_runtime_status_uses_isolated_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env["PLUGIN_DATA"] = str(Path(temp_dir) / "runtime")
            result = subprocess.run(
                [sys.executable, str(PLUGIN / "scripts" / "memory_runtime.py"), "status"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["runtime_version"], "turn-journal-v4")
            self.assertEqual(payload["anchors"], 0)

    def test_experience_store_initializes_in_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "experience.sqlite3"
            subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN / "scripts" / "memory_store.py"),
                    "--db",
                    str(database),
                    "list-domains",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertTrue(database.exists())


if __name__ == "__main__":
    unittest.main()
