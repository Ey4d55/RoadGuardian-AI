"""Validate the portable source manifest without camera, model or network I/O."""
import ast
from pathlib import Path
import unittest
from package_release import ROOT, SOURCES


class ReleaseTests(unittest.TestCase):
    def test_manifest_contains_runtime_modules_and_no_private_files(self):
        names = {name for name, _ in SOURCES}
        for name in ("tabletop_demo.py", "esp32_controller.ino", "road_region.example.json",
                     "requirements-dashboard.txt"):
            self.assertIn(name, names)
        for name in names:
            self.assertTrue((ROOT / name).is_file(), name)
            self.assertNotIn(".codex-remote-attachments", name)
            self.assertNotIn(name, ("edge_status.json", "road_region.json"))
        for name, language in SOURCES:
            if language == "python":
                tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
                for item in tree.body:
                    if isinstance(item, ast.ImportFrom) and item.module and (ROOT / (item.module + ".py")).exists():
                        self.assertIn(item.module + ".py", names)
