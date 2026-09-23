# tests/test_layout_extract.py
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from unittest.mock import patch

from app_profile import LayoutConstants, WECOM
from perception import TextBlock, extract_messages, read_conversation


class LayoutExtractTests(unittest.TestCase):
    def test_narrower_pane_excludes_left_block(self):
        # Vision bottom-origin y; extract converts to top-origin.
        blocks = [
            TextBlock("侧栏噪声", 1.0, x=0.20, y=0.50, w=0.08, h=0.04),
            TextBlock("对方消息", 1.0, x=0.40, y=0.50, w=0.20, h=0.04),
        ]
        wide = LayoutConstants(0.32, 0.30, 0.90, 0.24, ui_noise=())
        narrow = LayoutConstants(0.45, 0.43, 0.90, 0.24, ui_noise=())
        msgs_wide = extract_messages(blocks, layout=wide)
        # rebuild blocks — extract mutates y in place
        blocks2 = [
            TextBlock("侧栏噪声", 1.0, x=0.20, y=0.50, w=0.08, h=0.04),
            TextBlock("对方消息", 1.0, x=0.40, y=0.50, w=0.20, h=0.04),
        ]
        msgs_narrow = extract_messages(blocks2, layout=narrow)
        self.assertTrue(any("对方" in m.text for m in msgs_wide))
        self.assertFalse(any("对方" in m.text for m in msgs_narrow))

    def test_missing_window_error_uses_profile_display_name(self):
        with patch("perception.find_target_window", return_value=None) as find:
            res = read_conversation(profile=WECOM)
        find.assert_called_once_with(WECOM, None)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "企业微信 main window not found")


if __name__ == "__main__":
    unittest.main()
