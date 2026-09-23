# 企业微信（WeCom）支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让悬浮窗助手前台自动跟随个人微信或企业微信，全链路（读屏 → 判断 → 生成 → 展示 → 填入）对等可用，且不破坏 #50 精确匹配与纯只读原则。

**Architecture:** 新增 `AppProfile`（身份 + 布局 + 填入参数）；`frontmost_target()` / `find_target_window(profile, …)` 取代硬编码微信 API；HUD 以「当前 profile 或 None」为前台边界；布局与填入从 profile 读取。企微常量经本机探针标定后写死。

**Tech Stack:** Python 3.12、Quartz/AppKit/Vision、现有 `unittest` + `uv run`、无新依赖。

## Global Constraints

- 纯只读：不注入、不 hook、不解密企微/微信库；填入是唯一写动作。
- 填入：不剪贴板、不 Cmd+V、不自动发送；AX 优先；视觉路径需显式点击；读回确认；失败不重试；窗口/输入区/会话签名三重复核。
- Owner / 前台名：**精确匹配**，禁止子串（#50）。
- 轮询/停稳/`MIN_GAP_S`/分析独立线程：不得回退到 tick 线程阻塞。
- 企微布局常量以真机探针为准，禁止盲目长期依赖个微抄值而不标定。
- 用户可见行为变更须同步 README；`judge_zh_test` 意图口径不改。

---

## File map

| 文件 | 职责 |
|------|------|
| `src/app_profile.py` | `LayoutConstants` / `FillConstants` / `AppProfile`；`WECHAT` / `WECOM`；`PROFILES`；`resolve_profile(bundle, name)` |
| `src/perception.py` | `find_target_window` / `frontmost_target`；布局参数化；`read_conversation` 吃 profile |
| `src/fill.py` | `_target_app(profile)`；`locate_input` / `fill_text` 吃 profile |
| `src/visual_fill.py` | 窗校验用 `find_target_window(profile, …)` |
| `src/hud.py` | `_active_profile`；文案用 `display_name` |
| `src/generate.py` | prompt「聊天消息」 |
| `tests/test_app_profile.py` | resolve / 注册表 |
| `tests/test_wechat_window_identity.py` | 企微正式支持 + 兄弟仍排除 |
| `tests/test_target_window.py` | 按 profile 选窗、互不串窗 |
| `README.md` / `AGENTS.md` / `PRIVACY.md` | 双 IM、已知限制 |

---

### Task 1: `AppProfile` 数据模块

**Files:**
- Create: `src/app_profile.py`
- Create: `tests/test_app_profile.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) LayoutConstants` with fields: `chat_pane_x_min`, `sidebar_x_max`, `title_bar_y_max`, `input_area_y_min`, `me_x_min` (0.66), `me_x_soft` (0.50), `me_right_min` (0.80), `them_x_max` (0.50), `them_right_max` (0.80), `ui_noise: tuple[str, ...]`
  - `@dataclass(frozen=True) FillConstants` with: `preferred_chat_titles: tuple[str, ...]`, `input_role: str`, `min_input_area: float`, `visual_outline: bool`
  - `@dataclass(frozen=True) AppProfile` with: `id: str`, `display_name: str`, `app_names: tuple[str, ...]`, `bundle_id: str`, `preferred_window_titles: tuple[str, ...]`, `layout: LayoutConstants`, `fill: FillConstants`
  - `WECHAT: AppProfile`, `WECOM: AppProfile`, `PROFILES: tuple[AppProfile, ...] = (WECHAT, WECOM)`
  - `def resolve_profile(*, bundle: str = "", name: str = "") -> AppProfile | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app_profile.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -B -m unittest tests.test_app_profile -v`  
Expected: FAIL / `ModuleNotFoundError: No module named 'app_profile'`

- [ ] **Step 3: Write minimal implementation**

Create `src/app_profile.py`:

```python
"""IM app profiles: identity, layout, and fill parameters."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutConstants:
    chat_pane_x_min: float
    sidebar_x_max: float
    title_bar_y_max: float
    input_area_y_min: float
    me_x_min: float = 0.66
    me_x_soft: float = 0.50
    me_right_min: float = 0.80
    them_x_max: float = 0.50
    them_right_max: float = 0.80
    ui_noise: tuple[str, ...] = ()


@dataclass(frozen=True)
class FillConstants:
    preferred_chat_titles: tuple[str, ...]
    input_role: str = "AXTextArea"
    min_input_area: float = 10000.0
    visual_outline: bool = True


@dataclass(frozen=True)
class AppProfile:
    id: str
    display_name: str
    app_names: tuple[str, ...]
    bundle_id: str
    preferred_window_titles: tuple[str, ...]
    layout: LayoutConstants
    fill: FillConstants


_WECHAT_NOISE = (
    r"折叠聊天", r"共\s*\d+", r"搜索", r"发送", r"拖入文件", r"按住说话",
    r"语音输入文字", r"按住鼠标", r"按住 说话", r"输入文字",
    r"^[\w\-\u4e00-\u9fa5]{2,20}[:：].*\.\.\..*[）)]>$",
)

WECHAT_LAYOUT = LayoutConstants(
    chat_pane_x_min=0.32, sidebar_x_max=0.30,
    title_bar_y_max=0.90, input_area_y_min=0.24,
    ui_noise=_WECHAT_NOISE,
)

# Provisional WeCom layout: copy WeChat numbers until Task 6 probe overwrites them.
# Do not ship without completing Task 6 calibration.
WECOM_LAYOUT = LayoutConstants(
    chat_pane_x_min=0.32, sidebar_x_max=0.30,
    title_bar_y_max=0.90, input_area_y_min=0.24,
    ui_noise=_WECHAT_NOISE,
)

WECHAT = AppProfile(
    id="wechat",
    display_name="微信",
    app_names=("微信", "WeChat", "Weixin"),
    bundle_id="com.tencent.xinWeChat",
    preferred_window_titles=("微信", "WeChat", "Weixin"),
    layout=WECHAT_LAYOUT,
    fill=FillConstants(preferred_chat_titles=("微信", "WeChat", "Weixin")),
)

WECOM = AppProfile(
    id="wecom",
    display_name="企业微信",
    # Confirm owner strings in Task 6; keep exact match only.
    app_names=("企业微信", "WeChatWork", "WeCom"),
    bundle_id="com.tencent.WeWorkMac",
    preferred_window_titles=("企业微信", "WeChatWork", "WeCom"),
    layout=WECOM_LAYOUT,
    fill=FillConstants(preferred_chat_titles=("企业微信", "WeChatWork", "WeCom")),
)

PROFILES: tuple[AppProfile, ...] = (WECHAT, WECOM)


def resolve_profile(*, bundle: str = "", name: str = "") -> AppProfile | None:
    for p in PROFILES:
        if bundle and bundle == p.bundle_id:
            return p
    for p in PROFILES:
        if name and name in p.app_names:
            return p
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -B -m unittest tests.test_app_profile -v`  
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/app_profile.py tests/test_app_profile.py
git commit -m "$(cat <<'EOF'
feat(profile): 新增 AppProfile 注册表（个微 + 企微）

为前台跟随双 IM 抽出身份/布局/填入参数数据面。
EOF
)"
```

---

### Task 2: 感知层按 profile 选窗与前台解析

**Files:**
- Modify: `src/perception.py`（`WECHAT_APP_NAMES`、`frontmost_app_is_wechat`、`find_wechat_window`、模块顶部布局常量）
- Modify: `tests/test_wechat_window_identity.py`
- Create: `tests/test_target_window.py`

**Interfaces:**
- Consumes: `AppProfile`, `resolve_profile`, `WECHAT`, `WECOM`, `PROFILES` from `app_profile`
- Produces:
  - `def frontmost_target() -> AppProfile | None`
  - `def find_target_window(profile: AppProfile, previous_wid: int | None = None) -> WindowInfo | None`
  - Compatibility: `find_wechat_window(previous_wid=None)` → `find_target_window(WECHAT, previous_wid)`
  - Compatibility: `frontmost_app_is_wechat()` → `bool | None` where `True` means any supported IM is frontmost (rename semantics for HUD Task 5 — for this task keep returning True when `frontmost_target()` is not None, False when known other app, None on error). Document in docstring that name is historical.
  - Keep module-level `CHAT_PANE_X_MIN` etc. as aliases of `WECHAT.layout.*` for any probe scripts temporarily; mark for removal after Task 3.

- [ ] **Step 1: Write failing tests for WeCom selection**

Add to `tests/test_target_window.py`:

```python
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
```

Update `tests/test_wechat_window_identity.py`:
- Change `SIBLING_APPS = ("微信读书", "微信输入法")`（去掉企微）
- Keep existing WeChat tests using `find_wechat_window`
- Add assertion that `find_wechat_window` still rejects 企业微信 (wechat-only helper)

```python
def test_wechat_helper_still_rejects_wecom(self):
    self.assertIsNone(find_with([window("企业微信", "企业微信", 1200, 800)]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -B -m unittest tests.test_target_window -v`  
Expected: FAIL (`find_target_window` missing)

- [ ] **Step 3: Implement window + frontmost APIs**

In `src/perception.py`:

1. `from app_profile import WECHAT, resolve_profile, AppProfile`
2. Replace `WECHAT_APP_NAMES` with `WECHAT_APP_NAMES = WECHAT.app_names` (compat)
3. Replace `frontmost_app_is_wechat` body:

```python
def frontmost_target() -> AppProfile | None:
    try:
        import AppKit
        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return resolve_profile(
            bundle=app.bundleIdentifier() or "",
            name=app.localizedName() or "",
        )
    except Exception:
        return None


def frontmost_app_is_wechat() -> bool | None:
    """Historical name: True when any supported IM profile is frontmost."""
    try:
        import AppKit
        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return resolve_profile(
            bundle=app.bundleIdentifier() or "",
            name=app.localizedName() or "",
        ) is not None
    except Exception:
        return None
```

4. Implement `find_target_window(profile, previous_wid=None)` by copying `find_wechat_window` and replacing every `WECHAT_APP_NAMES` check with `profile.app_names`, and title priority with `profile.preferred_window_titles` (same membership test as today: `title in preferred_window_titles`).

5. Thin alias:

```python
def find_wechat_window(previous_wid: int | None = None) -> WindowInfo | None:
    return find_target_window(WECHAT, previous_wid)
```

- [ ] **Step 4: Run tests**

Run:
```bash
uv run python -B -m unittest tests.test_target_window tests.test_wechat_window_identity tests.test_app_profile -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/perception.py tests/test_target_window.py tests/test_wechat_window_identity.py
git commit -m "$(cat <<'EOF'
feat(perception): 按 AppProfile 选窗与解析前台目标

企业微信进入正式 profile；个微 helper 仍拒绝企微窗。
EOF
)"
```

---

### Task 3: 布局参数化进提取 / `read_conversation`

**Files:**
- Modify: `src/perception.py` — `_is_noise`, `message_side`, `extract_messages`, `_vision_blocks` ROI, `_fingerprint` crop, `read_conversation`
- Modify any tests that import module-level layout constants if they break

**Interfaces:**
- Consumes: `AppProfile.layout`
- Produces:
  - `message_side(x, width, layout: LayoutConstants | None = None)`
  - `extract_messages(..., layout: LayoutConstants | None = None)`
  - `_is_noise(b, layout: LayoutConstants | None = None)`
  - `read_conversation(..., profile: AppProfile | None = None)` — default `WECHAT` for CLI compat; uses `find_target_window(profile, …)` and `profile.layout`; return dict gains `"profile_id": profile.id`
  - Error string when window missing: `f"{profile.display_name} main window not found"`

- [ ] **Step 1: Write a focused unit test for layout-driven chat_pane**

```python
# tests/test_layout_extract.py
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import LayoutConstants
from perception import TextBlock, extract_messages


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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify fail** (missing `layout=` kwarg → TypeError)

Run: `uv run python -B -m unittest tests.test_layout_extract -v`

- [ ] **Step 3: Thread layout through helpers**

Default `layout=None` → use `WECHAT.layout`.

`message_side`:

```python
def message_side(x: float, width: float, layout: LayoutConstants | None = None) -> str:
    lay = layout or WECHAT.layout
    right = x + width
    if x >= lay.me_x_min or (x >= lay.me_x_soft and right >= lay.me_right_min):
        return "me"
    if x <= lay.them_x_max and right < lay.them_right_max:
        return "them"
    return "unknown"
```

`extract_messages`: filter with `lay.chat_pane_x_min`, `lay.input_area_y_min`, `lay.title_bar_y_max`; pass `layout` into `message_side` / `_is_noise`.

`_is_noise`: iterate `lay.ui_noise`.

`read_conversation`: add `profile: AppProfile | None = None`; `profile = profile or WECHAT`; `win = find_target_window(profile, previous_wid)`; pass `profile.layout` into extract/OCR ROI/fingerprint; include `"profile_id": profile.id` in success/unchanged returns. When calling `fill.locate_input`, pass `profile` (Task 4 will add the arg — for this task, if locate_input not yet updated, call without and fix in Task 4, OR do Task 3+4 in order with a temporary keyword-only default).

**Order note:** Implement `read_conversation(..., profile=...)` window/layout wiring here; keep `fill.locate_input(window)` unchanged until Task 4 (AX fallback still wechat-only briefly — acceptable for one commit if Task 4 follows immediately).

OCR ROI in `_vision_blocks`: add optional `layout` or use module alias still pointing at WECHAT until profile is threaded — prefer passing `chat_pane_x_min` / `input_area_y_min` from `read_conversation` into `ocr_image` → `_vision_blocks`.

Minimal approach for ROI: add optional kwargs `chat_pane_x_min=None`, `input_area_y_min=None` defaulting to `WECHAT.layout` values.

- [ ] **Step 4: Run tests**

```bash
uv run python -B -m unittest discover -s tests -v
```
Expected: PASS (fix any tests that assumed mutated global constants)

- [ ] **Step 5: Commit**

```bash
git add src/perception.py tests/test_layout_extract.py
git commit -m "$(cat <<'EOF'
feat(perception): 消息提取与读屏按 profile.layout 参数化

为企微独立布局常量铺路，默认仍走个微标定值。
EOF
)"
```

---

### Task 4: 填入层按 profile

**Files:**
- Modify: `src/fill.py`
- Modify: `src/visual_fill.py` — `window_is_current` / `write_text` accept profile
- Modify: `src/perception.py` — `read_conversation` AX fallback `fill.locate_input(window, profile)`

**Interfaces:**
- Produces:
  - `def _target_app(profile: AppProfile)`
  - `def locate_input(win, profile: AppProfile | None = None)`
  - `def fill_text(text, target=None, profile: AppProfile | None = None)`
  - Reasons use `profile.display_name`（默认 WECHAT）
  - `_find_input_box(pid, window_rect=None, profile=None)` uses `profile.fill.*`

- [ ] **Step 1: Write unit test for reason strings / preferred title selection logic**

If hard to unit-test AX, test a small pure helper:

```python
# tests/test_fill_profile.py
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app_profile import WECHAT, WECOM
import fill


class FillProfileTests(unittest.TestCase):
    def test_no_app_reason_uses_display_name(self):
        # ensure helper exists
        self.assertIn(WECOM.display_name, fill._reason_no_app(WECOM))
        self.assertIn(WECHAT.display_name, fill._reason_no_app(WECHAT))


if __name__ == "__main__":
    unittest.main()
```

Add in `fill.py`:

```python
def _reason_no_app(profile) -> str:
    return f"没找到{profile.display_name}应用"

def _reason_no_input(profile) -> str:
    return f"未取得可用的{profile.display_name}输入控件"
```

- [ ] **Step 2: Run fail then implement**

Refactor:
- `_wechat_app` → `_target_app(profile)` using `profile.bundle_id` / `profile.app_names`
- `locate_input(win, profile=None)` with `profile = profile or WECHAT`
- `_find_input_box`: title sort key uses `title not in profile.fill.preferred_chat_titles`; role/min area from `profile.fill`
- `fill_text`: resolve profile from `target.get("profile")` or arg; pass through to `locate_input`
- `visual_fill.window_is_current(win, app, require_front=False, profile=None)`: `find_target_window(profile or WECHAT, win['wid'])`
- Propagate `profile` into `write_text` from HUD target dict (`target["profile"] = profile`)

- [ ] **Step 3: Run offline tests**

```bash
uv run python -B -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add src/fill.py src/visual_fill.py src/perception.py tests/test_fill_profile.py
git commit -m "$(cat <<'EOF'
feat(fill): 填入与视觉校验按 AppProfile 寻址

错误文案与 AX 标题优先跟随当前 IM。
EOF
)"
```

---

### Task 5: HUD 前台边界改为 profile

**Files:**
- Modify: `src/hud.py`

**Interfaces:**
- Replace `self._wechat_frontmost: bool | None` with `self._active_profile: AppProfile | None`
- `_set_foreground_state(profile: AppProfile | None)` — clear when `profile` identity changes (`None` ↔ profile or wechat ↔ wecom). Compare by `(profile.id if profile else None)`.
- Tick paths: `profile = frontmost_target()`; `_set_foreground_state(profile)`; if `profile is None`: hide; else `read_conversation(..., profile=profile, previous_wid=...)`
- Status copy:
  - idle: `"等待消息…"`
  - leave: `f"{prev_display}不在前台"` — keep last display name or use generic `"聊天应用不在前台"` when profile becomes None (store `_last_display_name` on enter)
  - menu tip: `"jev-jarvis · 聊天意图助手"`
- On profile switch wechat↔wecom: same clear path as leave/enter (already cleared when id changes)
- Pass `profile` into fill target cache when locating input

- [ ] **Step 1: Implement HUD wiring (no pure unit test for AppKit panel — rely on identity tests + manual)**

Key edits (illustrative):

```python
from app_profile import AppProfile
from perception import frontmost_target, read_conversation, screen_capture_ok

IDLE_STATUS = "等待消息…"

# in __init__:
self._active_profile: AppProfile | None = None
self._last_display_name = "聊天应用"

def _set_foreground_state(self, profile: AppProfile | None):
    new_id = profile.id if profile else None
    old_id = self._active_profile.id if self._active_profile else None
    if new_id == old_id:
        return False
    prev_name = self._last_display_name
    self._active_profile = profile
    if profile is not None:
        self._last_display_name = profile.display_name
    # ... existing clear fields including _win_wid = None ...
    if profile is not None:
        self._next_read_ts = 0
        _log(f"前台切换 · {profile.display_name} 回到前台，强制重新读屏")
    else:
        _log(f"前台切换 · {prev_name} 离开前台，隐藏面板并清空旧结果")
        self._push("applyForegroundHidden:", f"{prev_name}不在前台")
    return True
```

Replace every `self._wechat_frontmost is True` with `self._active_profile is not None`.  
Replace `frontmost_app_is_wechat()` call sites with `frontmost_target()`.

In read path: `read_conversation(previous_wid=self._win_wid, ..., profile=self._active_profile)`.

When building fill target, set `target["profile"] = self._active_profile`.

- [ ] **Step 2: Smoke import**

Run: `uv run python -c "import hud; print('ok')"`  
Expected: `ok` (may need AppKit on macOS)

- [ ] **Step 3: Commit**

```bash
git add src/hud.py
git commit -m "$(cat <<'EOF'
feat(hud): 前台边界改为当前 AppProfile

个微/企微互切清缓存；文案跟随时显示名。
EOF
)"
```

---

### Task 6: 企微真机探针与布局标定

**Files:**
- Modify: `src/app_profile.py` — `WECOM.app_names` / titles / `WECOM_LAYOUT` / `fill` after probe
- Optionally add: `probe/wecom_probe.py` (list owner/title/bundle for WeCom windows)

**Manual steps (user machine has 企业微信):**

- [ ] **Step 1: Confirm identity**

```bash
osascript -e 'id of app "企业微信"'
# expect: com.tencent.WeWorkMac

uv run python - <<'PY'
import Quartz
from app_profile import resolve_profile
opts = Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements
for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID):
    owner = w.get("kCGWindowOwnerName") or ""
    if "企业" in owner or "WeWork" in owner or "WeCom" in owner or "WeChatWork" in owner:
        print(owner, "|", w.get("kCGWindowName"), "|",
              (w.get("kCGWindowBounds") or {}).get("Width"),
              (w.get("kCGWindowBounds") or {}).get("Height"))
print("resolve", resolve_profile(name="企业微信"))
PY
```

Update `WECOM.app_names` / `preferred_window_titles` / `fill.preferred_chat_titles` to **exact** live strings only (drop unused aliases).

- [ ] **Step 2: Calibrate layout with boxes**

1. 打开企微主聊天窗（侧栏 + 左右气泡 + 输入区）。
2. `JEV_BOXES=1 ./start.command`，前台切到企微。
3. 调 `WECOM_LAYOUT.chat_pane_x_min` / `input_area_y_min` / `title_bar_y_max` 直到框对准。
4. 点「填入」测 AX；若无控件，确认视觉路径读回成功；必要时调 `min_input_area`。
5. 在 `app_profile.py` 注释写明：`# Calibrated on 企业微信 <version> / macOS <version> / YYYY-MM-DD`

- [ ] **Step 3: Run offline tests + commit**

```bash
uv run python -B -m unittest discover -s tests -v
git add src/app_profile.py probe/wecom_probe.py  # if added
git commit -m "$(cat <<'EOF'
fix(wecom): 真机标定企微身份与布局常量

按探针结果收紧 app_names 并写入归一化布局。
EOF
)"
```

---

### Task 7: 生成文案 + 文档

**Files:**
- Modify: `src/generate.py` — `PROMPT_ONE` 首句改为「刚收到一条聊天消息」
- Modify: `README.md` — 支持个微+企微、前台跟随；已知限制删除「企业微信不参与」；补企微标定版本；真机自测清单
- Modify: `AGENTS.md` / `PRIVACY.md` — 「目标 IM 窗口」措辞，原则不变

- [ ] **Step 1: Edit generate prompt**

```python
PROMPT_ONE = """刚收到一条聊天消息，你要帮我回。
...
- 每条不超过 30 个字，是聊天里打字的语气，不要客套话、不要解释
```

- [ ] **Step 2: README 已知限制（替换相关条目）**

要点：
- 悬浮窗在**微信或企业微信**位于前台时显示；切到其他应用隐藏。
- 兄弟应用仍排除：微信读书、微信输入法（**不再**列企业微信为排除项）。
- 新增：企微布局按 `<version>` 标定；改版需重校准。
- 真机清单：企微框准、AX/视觉填入、两 App 互切、非目标隐藏。

- [ ] **Step 3: Run judge regression (prompt wording only in generate — still run)**

```bash
uv run python src/judge_zh_test.py
uv run python -B -m unittest discover -s tests -v
```

- [ ] **Step 4: Commit**

```bash
git add src/generate.py README.md AGENTS.md PRIVACY.md
git commit -m "$(cat <<'EOF'
docs: 文档与生成 prompt 覆盖企业微信前台跟随

同步已知限制与纯只读措辞到双 IM。
EOF
)"
```

---

### Task 8: 端到端验收（人工）

- [ ] **Step 1: Checklist**

| # | 步骤 | 期望 |
|---|------|------|
| 1 | 仅微信前台 | 与改前一致：读屏、候选、填入 |
| 2 | 仅企微前台 | 检测框准；候选出现；填入读回 OK |
| 3 | 微信 → Chrome | 面板隐藏 |
| 4 | Chrome → 企微 | 强制重读，无微信残留 |
| 5 | 企微 ↔ 微信 | 清缓存、不串窗、不串会话标题 |
| 6 | 微信读书前台 | 面板隐藏，不 OCR |

- [ ] **Step 2: Fix any calibration issues found; commit if needed**

---

## Self-review (plan vs spec)

| Spec 要求 | Task |
|-----------|------|
| App Profile | 1 |
| 前台自动跟随 / frontmost_target / find_target_window | 2, 5 |
| 布局进 profile + 真机标定 | 3, 6 |
| 填入 AX+视觉按 profile | 4, 6 |
| HUD 文案 / 互切清状态 | 5 |
| 生成 prompt / README / AGENTS / PRIVACY | 7 |
| 测试：身份、兄弟排除、互不串窗 | 1, 2 |
| 成功标准 E2E | 8 |
| 非目标（双面板/钉钉/解密） | 未列入任务 |

无 TBD 步骤；`WECOM` 初始布局为临时抄值，**Task 6 强制标定**后才算完成。
