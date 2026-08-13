"""Manifest, hook, documentation, and public-package contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "lorekiln"


class PluginContractTests(unittest.TestCase):
    def test_manifest_and_hooks_are_valid_and_cross_platform(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "lorekiln")
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        self.assertTrue(all(len(item) <= 128 for item in manifest["interface"]["defaultPrompt"]))
        expected = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}
        self.assertEqual(set(hooks["hooks"]), expected)
        for event in hooks["hooks"].values():
            command = event[0]["hooks"][0]
            self.assertIn("python3", command["command"])
            self.assertIn("${PLUGIN_ROOT}", command["command"])
            self.assertIn("powershell.exe", command["commandWindows"])
            self.assertIn("${PLUGIN_ROOT}", command["commandWindows"])

    def test_quick_start_commands_match_runtime_cli(self) -> None:
        readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        runtime_help = subprocess.run(
            [sys.executable, str(PLUGIN / "scripts" / "memory_runtime.py"), "--help"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        for command in ("doctor", "status", "list-anchors", "materialize-anchor"):
            self.assertIn(command, readme)
            self.assertIn(command, runtime_help)
        self.assertIn("doctor --support", readme)
        self.assertIn("Create a memory anchor now", readme)

    def test_public_package_privacy_check_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "check_public_package.py")],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
