#!/usr/bin/env python3
"""List WeCom windows and resolve_profile against live owner/bundle.

Run: uv run python -B probe/wecom_probe.py

Without Screen Recording, kCGWindowName is None for every window. That is a
macOS permission gate, not WeCom-specific product behavior — do not treat
empty titles as calibrated chat-window titles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import Quartz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import WECOM, resolve_profile  # noqa: E402

_OWNER_HINTS = ("WeCom", "企业微信", "WeWork", "WeChatWork")


def screen_capture_ok() -> bool:
    try:
        return bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:
        return False


def wecom_windows() -> list[dict]:
    opts = Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements
    rows = []
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID):
        owner = w.get("kCGWindowOwnerName") or ""
        if not any(h in owner for h in _OWNER_HINTS):
            continue
        b = dict(w.get("kCGWindowBounds") or {})
        rows.append({
            "owner": owner,
            "title": w.get("kCGWindowName"),
            "pid": w.get("kCGWindowOwnerPID"),
            "wid": w.get("kCGWindowNumber"),
            "w": b.get("Width", 0),
            "h": b.get("Height", 0),
            "layer": w.get("kCGWindowLayer"),
            "onscreen": bool(w.get("kCGWindowIsOnscreen", False)),
            "profile": getattr(resolve_profile(name=owner), "id", None),
        })
    return sorted(rows, key=lambda r: (r["w"] or 0) * (r["h"] or 0), reverse=True)


def main() -> int:
    scr = screen_capture_ok()
    report = {
        "screen_capture_ok": scr,
        "bundle_id": WECOM.bundle_id,
        "app_names": list(WECOM.app_names),
        "resolve_WeCom": getattr(resolve_profile(name="WeCom"), "id", None),
        "resolve_企业微信": getattr(resolve_profile(name="企业微信"), "id", None),
        "resolve_bundle": getattr(
            resolve_profile(bundle=WECOM.bundle_id), "id", None),
        "windows": wecom_windows(),
    }
    if not scr:
        report["title_note"] = (
            "titles probe under Screen Recording / HUD — "
            "empty kCGWindowName is the SCR gate, not WeCom")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
