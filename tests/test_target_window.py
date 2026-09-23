import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import WECHAT, WECOM
from perception import find_target_window


def window(owner, title, w, h, wid=1, pid=1):
    return {
        "kCGWindowOwnerName": owner, "kCGWindowName": title,
        "kCGWindowNumber": wid, "kCGWindowOwnerPID": pid,
        "kCGWindowBounds": {"X": 0, "Y": 0, "Width": w, "Height": h},
    }


def find_with(profile, windows, previous_wid=None):
    with patch("Quartz.CGWindowListCopyWindowInfo", return_value=windows):
        return find_target_window(profile, previous_wid)


class TargetWindowTests(unittest.TestCase):
    def test_wecom_window_found_for_wecom_profile(self):
        win = find_with(WECOM, [window("企业微信", "企业微信", 1200, 800, wid=7)])
        self.assertIsNotNone(win)
        self.assertEqual(win.wid, 7)

    def test_wechat_profile_ignores_wecom_window(self):
        self.assertIsNone(
            find_with(WECHAT, [window("企业微信", "企业微信", 1200, 800, wid=7)]))

    def test_wecom_profile_ignores_wechat_window(self):
        self.assertIsNone(
            find_with(WECOM, [window("微信", "微信", 949, 862, wid=1)]))

    def test_mixed_list_picks_matching_profile_only(self):
        wins = [
            window("微信", "微信", 949, 862, wid=1),
            window("企业微信", "企业微信", 1200, 800, wid=7),
        ]
        self.assertEqual(find_with(WECHAT, wins).wid, 1)
        self.assertEqual(find_with(WECOM, wins).wid, 7)


if __name__ == "__main__":
    unittest.main()
