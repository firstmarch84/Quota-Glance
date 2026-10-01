import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from providers import create_adapters, configure, selected


class ProviderTests(unittest.TestCase):
    @patch('bridge.ExtensionQuota')
    @patch('core.Codex')
    def test_codex_never_starts_claude_bridge(self, codex, claude):
        self.assertEqual(list(create_adapters({'providers':'codex'})), ['codex'])
        codex.assert_called_once()
        claude.assert_not_called()

    @patch('bridge.ExtensionQuota')
    @patch('core.Codex')
    def test_claude_never_creates_codex(self, codex, claude):
        self.assertEqual(list(create_adapters({'providers':'claude'})), ['claude'])
        codex.assert_not_called()
        claude.assert_called_once()

    def test_existing_install_defaults_to_both(self):
        self.assertEqual(selected({}), ['codex','claude'])

    def test_changes_selection_preserving_preferences(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            path.write_text('{"topmost":true}',encoding='utf-8')
            configure(path,'codex')
            self.assertEqual(json.loads(path.read_text()),{'topmost':True,'providers':'codex'})
            configure(path,'both')
            self.assertTrue(json.loads(path.read_text())['topmost'])

    def test_invalid_settings_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)/'settings.json'
            path.write_text('broken',encoding='utf-8')
            with self.assertRaises(ValueError):
                configure(path,'codex')
            self.assertEqual(path.read_text(),'broken')


if __name__ == '__main__':
    unittest.main()
