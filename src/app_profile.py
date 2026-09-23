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

# Identity calibrated 企业微信 5.0.11 / owner=WeCom / 2026-09-23.
# Layout still provisional (WeChat copy) pending JEV_BOXES HUD run with Screen Recording.
# This CLI has no SCR grant: titles are None and capture/OCR cannot calibrate boxes.
# Do not invent layout numbers; leave WeChat copy until a HUD boxes pass.
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

# Calibrated identity on 企业微信 5.0.11 / owner=WeCom / 2026-09-23
# Live kCGWindowOwnerName on this locale is WeCom (not 企业微信).
# WeChatWork dropped: not observed as owner on 5.0.11; WeCom is the current EN name.
# Titles: CLI has no Screen Recording so kCGWindowName is None — not product-empty.
# Keep title aliases; re-probe under Screen Recording / HUD (JEV_BOXES=1).
WECOM = AppProfile(
    id="wecom",
    display_name="企业微信",
    app_names=("WeCom", "企业微信"),
    bundle_id="com.tencent.WeWorkMac",
    preferred_window_titles=("WeCom", "企业微信"),
    layout=WECOM_LAYOUT,
    fill=FillConstants(preferred_chat_titles=("WeCom", "企业微信")),
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
