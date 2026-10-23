"""Prevent static Pages scenes from drifting away from the tested engine."""
import unittest
from pathlib import Path
from build_pages import LABELS
from traffic_simulation import component_html

class PagesTests(unittest.TestCase):
    def test_export_matches_source_for_all_scenarios(self):
        for key in LABELS:
            self.assertEqual(Path("docs/scenes/"+key.lower()+".html").read_text(encoding="utf-8"),component_html(key))
    def test_entry_references_existing_local_scenes(self):
        import re
        html=Path("docs/index.html").read_text(encoding="utf-8")
        for scene in re.findall(r'<option value="([a-z_]+)"',html):
            self.assertTrue(Path("docs/scenes/"+scene+".html").is_file())
        self.assertNotIn("127.0.0.1",html)
        self.assertNotIn("dist/",html)
