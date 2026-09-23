import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import PROFILES, WECHAT, WECOM, resolve_profile


class AppProfileTests(unittest.TestCase):
    def test_wechat_bundle_resolves(self):
        self.assertIs(resolve_profile(bundle="com.tencent.xinWeChat"), WECHAT)

    def test_wecom_bundle_resolves(self):
        self.assertIs(resolve_profile(bundle="com.tencent.WeWorkMac"), WECOM)

    def test_exact_owner_names(self):
        for name in WECHAT.app_names:
            self.assertIs(resolve_profile(name=name), WECHAT)
        for name in WECOM.app_names:
            self.assertIs(resolve_profile(name=name), WECOM)

    def test_sibling_names_rejected(self):
        for name in ("微信读书", "微信输入法"):
            self.assertIsNone(resolve_profile(name=name))

    def test_profiles_unique_ids(self):
        ids = [p.id for p in PROFILES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {"wechat", "wecom"})


if __name__ == "__main__":
    unittest.main()
