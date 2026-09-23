import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import perception
from app_profile import WECHAT, WECOM
from perception import find_target_window, find_wechat_window


def window(owner, title, w, h, wid=1, pid=1):
    return {
        "kCGWindowOwnerName": owner, "kCGWindowName": title,
        "kCGWindowNumber": wid, "kCGWindowOwnerPID": pid,
        "kCGWindowBounds": {"X": 0, "Y": 0, "Width": w, "Height": h},
    }


def find_with(profile, windows, previous_wid=None):
    with patch("Quartz.CGWindowListCopyWindowInfo", return_value=windows):
        return find_target_window(profile, previous_wid)


def find_wechat_with(windows, previous_wid=None):
    with patch("Quartz.CGWindowListCopyWindowInfo", return_value=windows):
        return find_wechat_window(previous_wid)


class _FakeApp:
    def __init__(self, name, bundle):
        self._name, self._bundle = name, bundle

    def bundleIdentifier(self):
        return self._bundle

    def localizedName(self):
        return self._name


class _FakeWorkspace:
    def __init__(self, app):
        self._app = app

    def frontmostApplication(self):
        return self._app


def frontmost_target(name, bundle=""):
    """frontmost_target() against a synthetic NSWorkspace; queries no real app."""
    appkit = types.ModuleType("AppKit")
    appkit.NSWorkspace = SimpleNamespace(
        sharedWorkspace=lambda: _FakeWorkspace(_FakeApp(name, bundle)))
    with patch.dict(sys.modules, {"AppKit": appkit}):
        return perception.frontmost_target()


def frontmost_app_is_wechat(name, bundle=""):
    """frontmost_app_is_wechat() against a synthetic NSWorkspace; queries no real app."""
    appkit = types.ModuleType("AppKit")
    appkit.NSWorkspace = SimpleNamespace(
        sharedWorkspace=lambda: _FakeWorkspace(_FakeApp(name, bundle)))
    with patch.dict(sys.modules, {"AppKit": appkit}):
        return perception.frontmost_app_is_wechat()


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

    def test_wechat_helper_rejects_wecom_owner_strings(self):
        for owner in ("企业微信", "WeChatWork", "WeCom"):
            with self.subTest(owner=owner):
                self.assertIsNone(find_wechat_with([window(owner, owner, 1200, 800)]))

    def test_frontmost_target_wechat_by_name(self):
        for name in perception.WECHAT_APP_NAMES:
            with self.subTest(name=name):
                profile = frontmost_target(name)
                self.assertIs(profile, WECHAT)

    def test_frontmost_target_wechat_by_bundle(self):
        profile = frontmost_target("Some Locale Name", bundle="com.tencent.xinWeChat")
        self.assertIs(profile, WECHAT)

    def test_frontmost_target_wecom_by_name(self):
        for name in WECOM.app_names:
            with self.subTest(name=name):
                self.assertIs(frontmost_target(name), WECOM)

    def test_frontmost_target_wecom_by_bundle(self):
        profile = frontmost_target("WeCom", bundle="com.tencent.WeWorkMac")
        self.assertIs(profile, WECOM)

    def test_frontmost_target_rejects_sibling_app(self):
        self.assertIsNone(frontmost_target("微信读书", bundle="com.tencent.weread"))

    def test_frontmost_app_is_wechat_true_when_wecom_frontmost(self):
        self.assertTrue(frontmost_app_is_wechat("企业微信"))
        self.assertTrue(frontmost_app_is_wechat("WeCom", bundle="com.tencent.WeWorkMac"))


if __name__ == "__main__":
    unittest.main()
