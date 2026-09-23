# 企业微信（WeCom）支持 — 设计说明

日期：2026-09-23  
状态：已评审（对话确认）  
范围：在保持纯只读原则下，让悬浮窗助手前台自动跟随个人微信或企业微信，全链路对等（读屏 → 判断 → 生成 → 展示 → 填入）。

## 背景与目标

当前实现把个人微信（`com.tencent.xinWeChat`，owner 精确名 `微信` / `WeChat` / `Weixin`）硬编码进感知、填入与 HUD。企业微信曾因 #50 子串误匹配被列入兄弟应用排除名单。

**目标行为（已确认）**

- **A · 前台自动跟随**：前台是微信则读微信，前台是企微则读企微；两者同时开着时随焦点切换。
- **全链路对等**：OCR → 意图/风险判断 → 候选生成 → 悬浮窗 → 一键填入（AX 优先，视觉回退）。
- **本机可标定**：实现阶段用已安装的企业微信做布局与填入探针。

**非目标（本版不做）**

- 同时为两个 App 各挂一个面板，或后台非前台 App 继续分析。
- 企微全屏特殊布局、多账号双开。
- 钉钉 / 飞书等其它 IM（只保留 profile 扩展点）。
- 解密企微本地库、注入、hook、自动发送；不改回剪贴板 + Cmd+V。

## 方案选择

采用 **App Profile**（相对「散落 if/else」或「整文件双轨复制」）：

- 身份、布局、填入参数收成数据。
- HUD 按前台选当前 profile，管线其余逻辑复用。
- 日后加 IM 只加 profile，不改轮询/停稳/预判骨架。

## 架构

```text
前台 App
  → resolve_profile()          # bundle / 精确 owner 名
  → find_target_window(profile, previous_wid)
  → read_conversation(..., layout=profile.layout)
  → judge / generate（与现网相同）
  → HUD 展示（文案按 profile.display_name）
  → fill_text / visual_fill（profile.fill）
```

硬约束沿用 AGENTS.md：纯只读；轮询/停稳/`MIN_GAP_S`；分析在独立线程；填入三重复核 + OCR 读回、失败不重试。

### `AppProfile` 形状

```text
id: "wechat" | "wecom"
display_name: "微信" | "企业微信"     # 用户可见文案
app_names: tuple[str, ...]           # owner 精确匹配，禁止子串
bundle_id: str
preferred_window_titles: tuple[str, ...]  # 主聊天窗标题优先
layout: LayoutConstants
fill: FillConstants
```

**`LayoutConstants`**：`chat_pane_x_min`、`sidebar_x_max`、`title_bar_y_max`、`input_area_y_min`、气泡左右阈值（或沿用 `message_side` 可配置阈值）、`ui_noise` 模式元组。

**`FillConstants`**：`preferred_chat_titles`、`input_role`（默认 `AXTextArea`）、`min_input_area`、是否启用视觉 `input_outline`（及必要时的阈值覆盖）。

个微 profile 的数值取自现有常量（WeChat 4.1 已标定）。企微 profile 的 bundle 预期为 `com.tencent.WeWorkMac`；`app_names` / 窗标题 / 布局数值以真机探针为准后写死，并在 README 注明标定版本。

## 身份与前台切换

1. `frontmost_target()`（或等价名）：命中则返回对应 `AppProfile`，否则 `None`（行为等同今日「微信不在前台」）。
2. `find_target_window(profile, previous_wid)`：仅在该 profile 的 `app_names` 内选窗；规则保留：非空标题、≥600×400、标题优先、面积、`previous_wid` 粘性。
3. 个微 ↔ 企微互切：视为离开原目标 IM —— 清指纹/缓存、重置 sticky wid、强制重读（复用 `_set_foreground_state` 边界语义，状态字段从「是否微信前台」泛化为「当前 profile 或 None」）。
4. 兄弟应用：微信读书、微信输入法等仍不进任何 profile；企业微信从排除名单进入正式 `wecom` profile。
5. API：`find_wechat_window` / `frontmost_app_is_wechat` 收到通用名；必要时保留薄别名以免一次改爆调用点。

## 布局标定

- 布局常量进入 profile；`extract_messages` / OCR ROI / 指纹裁剪等读 `layout`，不再依赖模块级全局写死。
- 坐标系（Vision 底原点、CGImage 顶原点）、仅 `zh-Hans`、Accurate、1x nominal 采集不变。
- **标定流程**（实现阶段）：
  1. 探针确认 owner 名、bundle、主窗标题、典型尺寸。
  2. 标准聊天窗（侧栏 + 左右气泡 + 输入区）。
  3. `JEV_BOXES=1` 对齐检测框，调归一化常量。
  4. 写入 `WECOM` profile；README「已知限制」写明企微版本。
- 首版不盲目抄个微常量；侧栏差大时优先调 `chat_pane_x_min` 等边界。
- `ui_noise` 仅在确认企微特有 UI 文案后追加。

## 填入

硬约束不变：不剪贴板、不 Cmd+V、不自动发送；AX 优先；显式「填入」才可走 `visual_fill`；读回确认；失败不重试；窗口 / 输入区 / 会话签名三重复核。

1. `locate_input(window, profile)`：按 profile 找 AX；失败则挂 `visual_rect` / `chat_signature`。
2. `fill_text(..., profile)`：用 profile 的 bundle / names；错误文案用 `display_name`。
3. `visual_fill` 窗校验改为 `find_target_window(profile, …)`。
4. 企微 AX role / `min_input_area` / 分隔线算法以真机为准；`input_outline` 先复用，不达标再加 profile 级阈值，不改回剪贴板路径。

## HUD 与文案

- 状态行按 profile：`等待消息…`；离开前台 → `{display_name}不在前台`。
- 菜单 tip：产品名保留，语义改为支持双 IM（例如「聊天意图助手」）。
- 生成 prompt 中「微信消息」可改为「聊天消息」；**不改**意图枚举与 `judge_zh_test` 口径。
- 判断层 / 生成本身无 App 特化；仅消费感知层抽出的文本。

## 测试与文档

| 项 | 动作 |
|----|------|
| `tests/test_wechat_window_identity.py` | 企微移出 `SIBLING_APPS`；断言个微/企微各自精确匹配、互不串窗；读书/输入法仍排除 |
| 新增 | profile 解析、选窗粘性、切换清状态（mock 窗列表） |
| 现有离线回归 | `judge_zh_test`、outgoing 等保持绿 |
| 真机清单（README / PR） | 企微框准、AX/视觉填入、两 App 互切、非目标 App 时隐藏 |

文档：README 写明双支持与前台跟随，去掉「企业微信不参与窗口选择」；`AGENTS.md` / `PRIVACY.md` 措辞改为「目标 IM 窗口」，原则仍为纯只读。发版资产命名不变。

## 文件落点（预期）

- 新增：`src/app_profile.py`（或 `src/profiles.py`）— profile 定义与注册表。
- 改：`src/perception.py`、`src/fill.py`、`src/visual_fill.py`、`src/input_region.py`（若需阈值）、`src/hud.py`、`src/generate.py`（文案）、相关 tests、README / AGENTS / PRIVACY。
- probe 脚本可随后改为按 profile 枚举（非阻塞本版上线）。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 企微布局与个微差异大，OCR 框偏 | 真机标定；检测框可视化验收；常量进 profile 易改 |
| 企微无 AXTextArea | 视觉路径已存在；验收两条路径 |
| 切换时用到过期窗 / 错填 | sticky wid 按 profile 重置；填入三重复核 |
| 破坏 #50 精确匹配 | 单测锁死兄弟应用；禁止子串 owner 匹配 |
| 判断冷启动与企微无关 | 不在本版范围；勿误判为回归 |

## 成功标准

1. 前台个微：行为与现网一致（读屏、候选、填入）。
2. 前台企微：全链路可用；检测框对准消息；填入读回成功。
3. 两 App 来回切换：面板不串内容、不串窗。
4. 前台为 Chrome 等：面板隐藏，与今日一致。
5. 离线 CI / `judge_zh_test` 不回归。
