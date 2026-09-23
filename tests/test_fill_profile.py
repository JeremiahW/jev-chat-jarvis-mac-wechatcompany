import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import WECHAT, WECOM
import fill
import perception as p
import visual_fill


class FillProfileTests(unittest.TestCase):
    def test_no_app_reason_uses_display_name(self):
        self.assertIn(WECOM.display_name, fill._reason_no_app(WECOM))
        self.assertIn(WECHAT.display_name, fill._reason_no_app(WECHAT))

    def test_no_input_reason_uses_display_name(self):
        self.assertIn(WECOM.display_name, fill._reason_no_input(WECOM))
        self.assertIn(WECHAT.display_name, fill._reason_no_input(WECHAT))

    def test_preferred_title_sort_puts_chat_window_first(self):
        titles = ["未命名", "企业微信", "WeCom"]
        ordered = sorted(titles, key=lambda t: fill._title_sort_key(t, WECOM))
        self.assertIn(ordered[0], WECOM.fill.preferred_chat_titles)
        self.assertEqual(ordered[-1], "未命名")
        self.assertTrue(fill._title_sort_key("企业微信", WECHAT))
        self.assertFalse(fill._title_sort_key("微信", WECHAT))

    def test_locate_input_no_app_reason_follows_profile(self):
        with patch.object(fill, "has_accessibility", return_value=True), \
             patch.object(fill, "_target_app", return_value=None):
            result = fill.locate_input({"x": 0, "y": 25, "w": 800, "h": 600}, WECOM)
        self.assertIsNone(result["box"])
        self.assertIn(WECOM.display_name, result["reason"])
        self.assertIs(result["profile"], WECOM)

    def test_fill_text_resolves_profile_from_target(self):
        target = {"window": {}, "box": None, "visual_rect": (0, 100, 600, 200),
                  "profile": WECOM}
        with patch.object(fill, "has_accessibility", return_value=True), \
             patch.object(fill, "_target_app", return_value=Mock()) as app_fn, \
             patch("visual_fill.write_text", return_value=(True, "已填入")) as write:
            ok, reason = fill.fill_text("hello", target=target)
        self.assertTrue(ok)
        self.assertEqual(reason, "已填入")
        app_fn.assert_called_once_with(WECOM)
        self.assertIs(write.call_args.args[1].get("profile"), WECOM)

    def test_window_is_current_uses_find_target_window_with_profile(self):
        win = {"wid": 7, "x": 0, "y": 0, "w": 800, "h": 600}
        app = Mock()
        app.processIdentifier.return_value = 10
        current = Mock(wid=7, pid=10, x=0, y=0, w=800, h=600)
        with patch.object(p, "find_target_window", return_value=current) as find:
            self.assertTrue(visual_fill.window_is_current(win, app, profile=WECOM))
        find.assert_called_once_with(WECOM, 7)

    def test_write_text_passes_profile_to_window_check(self):
        with patch.object(visual_fill, "window_is_current", return_value=False) as current, \
             patch.object(visual_fill.Q, "CGEventPost") as post:
            ok, reason = visual_fill.write_text(
                "hello", {"window": {}, "profile": WECOM}, Mock())
        self.assertFalse(ok)
        self.assertIn(WECOM.display_name, reason)
        post.assert_not_called()
        self.assertIs(current.call_args.kwargs.get("profile"), WECOM)

    def test_read_conversation_passes_profile_to_locate_input(self):
        win = p.WindowInfo(wid=1, pid=1, title="企业微信", x=0, y=0, w=800, h=600)
        with patch.object(p, "find_target_window", return_value=win), \
             patch.object(p, "capture_image", return_value=Mock()), \
             patch("input_region.input_outline", return_value=None), \
             patch("fill.locate_input", return_value={"rect": None}) as locate, \
             patch.object(p, "ocr_image", return_value=[]):
            p.read_conversation(profile=WECOM)
        locate.assert_called_once()
        self.assertIs(locate.call_args.args[1], WECOM)


if __name__ == "__main__":
    unittest.main()
