# VECTSPACE 协作开发说明（中文）

## 1. 项目结构

- `src/engine/app.py`: 应用入口，初始化资源根目录和默认字体。
- `src/engine/window.py`: 主窗口装配 `GameView` 与 `SceneManager`。
- `src/engine/scene_manager.py`: 根据场景名加载 Python 场景脚本并启动执行器。
- `src/engine/script/loader.py`: 读取并规范化 Python 场景脚本。
- `src/engine/script/runner.py`: 核心流程执行（节点调度、打字机、样式与速度）。
- `src/engine/ui/game_view.py`: 画面层与点击推进事件。
- `src/engine/ui/dialogue_text.py`: Web 对话渲染（KaTeX、动画标签、复制拦截）。
- `game/scripts/scenes/*.py`: 场景脚本。
- `game/assets/*`: 背景、字体、UI、KaTeX 离线资源。

## 2. 场景脚本格式

顶层字段：

- `nodes`: 节点字典（`id -> node`）
- `flow`: 节点播放顺序（按 `nodes` 的 key）
- `defaults`（可选）: 全局默认参数

### 2.1 `say` 节点

```json
{
  "type": "say",
  "speaker": "角色名",
  "text": "普通文本 $x^2+1$ <shake>抖动文本</shake>"
}
```

说明：

- 支持 `$...$` 内联公式。
- 支持受控 HTML 标签（见第 4 节）。
- 默认使用打字机效果。

### 2.2 `formula` 节点

```json
{
  "type": "formula",
  "latex": "\\int_0^1 x^2 dx"
}
```

说明：

- 显示独立公式块。
- 显示完成后等待点击推进。

### 2.3 `bg` 节点

```json
{
  "type": "bg",
  "file": "bg_vstest.png"
}
```

说明：

- 背景立即切换，不等待点击，自动进入下一个节点。

### 2.4 `style` 节点

```json
{
  "type": "style",
  "font_size": 36,
  "color": "#FFD166",
  "name_font_size": 40,
  "name_color": "#8BE9FD"
}
```

可用字段：

- 对话正文：`font_size` / `text_size`，`color` / `text_color`
- 姓名框：`name_font_size` / `name_size`，`name_color`

### 2.5 `typing` 节点

```json
{
  "type": "typing",
  "speed_ms": 24
}
```

或：

```json
{
  "type": "typing",
  "cps": 45
}
```

可用字段：

- `speed_ms` / `type_interval_ms` / `interval_ms`
- `cps` / `chars_per_second`
- `sfx` / `sfx_enabled` / `type_sfx`：是否启用打字音效
- `sfx_volume`：音量（`0.0 ~ 1.0`）
- `sfx_file` / `type_sfx_file`：音效文件名或路径（默认 `sfx/sfx_typing.wav`）
- `sfx_folder` / `type_sfx_folder`：配合 `sfx_file` 指定子目录
- `sfx_min_interval_ms` / `type_sfx_min_interval_ms`：最小触发间隔（毫秒，避免过密播放）

## 3. `defaults` 默认配置

```json
{
  "defaults": {
    "style": {
      "font_size": 35,
      "color": "#FFFFFF"
    },
    "typing": {
      "speed_ms": 30
    }
  }
}
```

## 4. 对话标签与动画

受支持标签：

- 基础标签：`<span class="...">`、`<b>`、`<i>`、`<u>`、`<em>`、`<strong>`、`<small>`、`<sup>`、`<sub>`、`<br>`
- 动画简写：`<shake>`、`<wave>`、`<pulse>`、`<glow>`、`<rainbow>`

动画简写会映射为：

- `<shake>` -> `<span class="fx-shake">`
- `<wave>` -> `<span class="fx-wave">`
- `<pulse>` -> `<span class="fx-pulse">`
- `<glow>` -> `<span class="fx-glow">`
- `<rainbow>` -> `<span class="fx-rainbow">`

示例：

```json
{
  "type": "say",
  "speaker": "?",
  "text": "普通 <span class=\"fx-glow\">发光</span> <shake>抖动</shake> $e^{i\\pi}+1=0$"
}
```

## 5. 安全与限制

- 对话中的 HTML 不是全量开放：只放行白名单标签与 `span.class`。
- `script`、事件属性、任意 style 注入都不会被解析通过。
- 对话区域已禁复制（鼠标选择/右键/快捷键）。

## 6. 常见协作建议

- 新增节点类型时，优先在 `ScriptRunner._show_current_node()` 分支中处理。
- 若节点需要全局默认值，统一接入 `ScriptRunner._apply_defaults()`。
- 调整对话渲染行为时，先看 `dialogue_text.py` 的：
  - `parse_dialogue_segments`
  - `count_reveal_units`
  - `_segments_to_markdown`
- 提交前建议至少做一次语法检查：

```powershell
python -m py_compile src/engine/**/*.py
```

## 7. 开发阶段标签放行

- `DialogueText` 解析 `<tag>` 时，默认在开发环境（未打包）放行全部标签。
- 打包环境默认仍使用安全白名单。
- 可通过环境变量覆盖：
  - `VECTSPACE_ALLOW_ALL_HTML_TAGS=1`：无条件放行全部标签
  - `VECTSPACE_FORCE_SAFE_HTML_TAGS=1`：无条件启用白名单

## 8. 打字停顿（pause）

- 在 `say.text` 中可以插入 `<pause .../>`，用于让打字机在该位置停顿一段时间。
- 停顿标签不会渲染到对话文本，也不会占用字符 reveal 进度。
- 点击左键时，如果当前句还有后续停顿点，会直接跳到“同一句的下一个停顿点”；如果没有后续停顿，则直接补全本句。

示例：

```json
{
  "type": "say",
  "speaker": "?",
  "text": "第一段<pause ms=\"800\"/>第二段<pause 1.2s/>第三段"
}
```

支持时长写法：

- `<pause/>`：默认 `500ms`
- `<pause ms=\"750\"/>`
- `<pause s=\"1.5\"/>`
- `<pause 1.2s/>`（无键名时按秒解析）

## 9. 行内改打字速度（speed）
- 在 `say.text` 中可插入 `<speed .../>`，用于从该位置开始修改后续打字速度。
- `speed` 标签不渲染到文本，也不占用 reveal 单位。

示例：
```json
{
  "type": "say",
  "speaker": "?",
  "text": "正常速度 <speed ms=\"18\"/>加速段 <speed cps=\"20\"/>恢复较慢段"
}
```

支持写法：
- `<speed ms=\"20\"/>`
- `<speed cps=\"40\"/>`
- `<speed 16ms/>`
- `<speed 30/>`（无单位时按 `ms`）
- `<speed -1/>`（切换为“完整单位推进”模式）

说明：
- “完整单位推进”会把每次打字推进改为一个完整单元：
  - 普通文本：推进到当前文本段末尾
  - 公式（`$...$` / `$$...$$`）：按整个公式块推进
- 后续再次使用正数 `<speed .../>` 会退出该模式并恢复按字符推进。

## 10. Python 场景脚本

当前仅支持 Python 场景文件：
- `game/scripts/scenes/<scene_name>.py`

Python 场景模块支持以下入口（按优先级）：
- `build_scene()` 函数
- `SCENE`
- `scene`
- `SCRIPT`
- `script`

返回值支持：
- 图结构：`{"nodes": ..., "flow": ...}`
- 线性结构：`{"id": "...", "defaults": {...}, "script": [...]}`
- 直接线性列表：`[...]`

线性结构每一项可以是：
- `dict` 节点（如 `{"type": "say", ...}`）
- Python `callable`（自动转成 `{"type": "call", "fn": ...}`）

`call` 节点说明：
- `type="call"` 时，执行 `fn` / `callable` / `function` 字段对应函数。
- 回调支持以下签名：
  - `def fn()`
  - `def fn(runner)`
  - `def fn(runner, node)`

`jump` 节点说明：
- `type="jump"` 时，可跳转到另一个场景脚本文件。
- 常用字段：`scene`（也兼容 `target` / `to` / `ref` / `file`）。
- 示例：`{"type": "jump", "scene": "Ch1/loop1"}`。

`wait` / `wait_click` 节点说明：
- `type="wait"`：自动等待一段时间后继续到下一个节点。
- `type="wait_click"`：空白间隔节点，不改任何显示内容，只在点击一次后继续。
- `wait` 常用字段：
  - `duration_ms` / `ms` / `time_ms` / `time`
  - `s` / `sec` / `second` / `seconds`
- 示例：
  - `{"type": "wait", "duration_ms": 800}`
  - `{"type": "wait", "s": 1.5}`
  - `{"type": "wait_click"}`

`dialogue_ui_show` / `dialogue_ui_hide` 节点说明：
- 用于控制文本框 UI（对话框底图、姓名框、文本区域）从底部滑入/滑出。
- 常用字段：`duration_ms`、`easing`、`wait`。
- 示例：
  - `{"type": "dialogue_ui_hide", "duration_ms": 220, "easing": "in_quad", "wait": true}`
  - `{"type": "dialogue_ui_show", "duration_ms": 220, "easing": "out_quad", "wait": true}`

## 11. Generator 场景脚本（推荐）

推荐直接用 `yield` 产出节点，而不是手写 `nodes/flow`：

```python
from src.engine.script.api import bg, jump, say, style, typing, wait, wait_click

SCENE_ID = "demo"
DEFAULTS = {
    "typing": {"speed_ms": 30},
    "style": {"font_size": 33, "color": "#FFFFFF"},
}


def query_count() -> int:
    return 3


def build_scene():
    yield bg("bg_vstest.png")

    # 可以直接写 Python 分支
    if query_count() > 0:
        yield say("System", "进入循环演示")

    # 可以直接写 for/while
    for i in range(query_count()):
        yield say("?", f"第 {i + 1} 句")

    n = 2
    while n > 0:
        yield say("?", f"while 倒计时 {n}")
        n -= 1

    yield wait(ms=600)
    yield wait_click()

    yield typing(speed_ms=18)
    yield style(color="#F5A9B8")
    yield say("?", "后续文本会使用新速度和样式")
    yield jump("Ch1/loop1")
```

说明：

- `loader` 会自动把 generator 产出的线性节点规范化为 `nodes/flow`，无需手动转换。
- 若需要默认配置，可在模块顶层定义 `SCENE_ID`、`DEFAULTS`。
- `build_scene()` 也可以返回 `dict`（`{"id":..., "defaults":..., "script": ...}`）或现成 `nodes/flow`。

## 12. 图片/立绘系统

脚本节点新增：

- `image_register`：注册图片资源与初始状态（默认不显示）
- `image_show`：显示图片，可附带位移/缩放/透明度动画
- `image_hide`：隐藏图片，可附带淡出/位移动画
- `image_transform`：仅做变换（位置、缩放、透明度、Z）
- `image_remove`：移除单个图片
- `image_clear`：清空所有图片

层级约定：

- 背景始终最下层
- 立绘图片层位于背景之上
- UI（对话框、姓名、文本）始终在立绘层之上

### 12.1 常用字段

通用 id 字段：`id`（兼容 `image_id` / `sprite_id` / `name`）

常用变换字段：

- 绝对位置：`x`, `y`
- 相对位移：`dx`, `dy`
- 缩放：`scale`（绝对）, `dscale`（相对）
- 透明度：`opacity`（绝对）, `dopacity`（相对）
- 层级：`z`
- 缓动：`easing`
- 时长：`duration_ms`
- 是否阻塞流程：`wait`（`true` 时等待动画完成后再进入下一节点）

`easing` 支持示例：

- `linear`, `in_quad`, `out_quad`, `in_out_quad`
- `in_cubic`, `out_cubic`, `in_out_cubic`
- `in_sine`, `out_sine`, `in_out_sine`
- `in_back`, `out_back`, `in_out_back`
- `out_bounce`, `in_out_bounce`, `out_elastic`

### 12.2 Generator 写法示例

```python
from src.engine.script.api import (
    bg,
    say,
    image_register,
    image_show,
    image_transform,
    image_hide,
)


def build_scene():
    yield bg("line1.png")
    yield image_register(
        "alice",
        "char_alice.png",
        folder="VECTORSPACE_pic",
        x=960,
        y=1040,
        scale=0.82,
        z=10,
    )
    yield image_show(
        "alice",
        opacity=1.0,
        duration_ms=260,
        easing="out_quad",
        wait=True,
    )
    yield say("Alice", "我出场了。")
    yield image_transform(
        "alice",
        dx=-140,
        dscale=0.05,
        duration_ms=220,
        easing="in_out_sine",
    )
    yield image_hide("alice", duration_ms=180, easing="in_quad")
```

## 13. 额外文本框（无 UI）

可注册额外文本框（纯文本区域，无对话框底图），渲染方式与主文本框一致（同 `DialogueTextView`，支持 `$...$`、`$$...$$`、标签动画等）。

脚本节点：

- `textbox_register` / `extra_textbox_register`
- `textbox_set_text` / `extra_textbox_set_text`
- `textbox_show` / `extra_textbox_show`
- `textbox_hide` / `extra_textbox_hide`
- `textbox_transform` / `extra_textbox_transform`
- `textbox_remove` / `extra_textbox_remove`
- `textbox_clear` / `extra_textbox_clear`

常用字段：

- 注册范围：`rect_x`, `rect_y`, `rect_w`, `rect_h`（也可用 `rect=[x,y,w,h]`）
- 变换：`x/y`, `dx/dy`, `scale/dscale`, `opacity/dopacity`, `z`
- 动画：`duration_ms`, `easing`, `wait`

示例（Generator）：

```python
from src.engine.script.api import (
    textbox_register,
    textbox_set_text,
    textbox_show,
    textbox_transform,
    textbox_hide,
)


def build_scene():
    yield textbox_register(
        "hint",
        rect_x=1400,
        rect_y=120,
        rect_w=420,
        rect_h=220,
        text="初始提示",
        font_size=28,
        color="#FFFFFF",
        opacity=0.0,
        z=30,
    )
    yield textbox_show("hint", opacity=1.0, duration_ms=220, easing="out_quad")
    yield textbox_set_text("hint", "这是一个额外文本框：$E=mc^2$")
    yield textbox_transform("hint", dy=30, duration_ms=180, easing="in_out_sine")
    yield textbox_hide("hint", duration_ms=180, easing="in_quad")
```

## 14. 存档系统（SaveSystem）

存档由 `SaveSystem + SceneManager` 协作完成：

- `SaveSystem` 负责槽位文件读写（默认目录：`game/saves/`）。
- `SceneManager.create_save_payload()` 导出当前场景快照。
- `SceneManager.load_save_payload()` 恢复场景快照与持久化变量。

### 14.1 槽位与文件

- 槽位数固定为 30（`slot_01.json` ~ `slot_30.json`）。
- 默认存档目录：`game/saves/`。
- 写入时会自动补齐：`slot_index`、`title`、`saved_at`。

### 14.2 存档 payload 结构

```json
{
  "scene_name": "prologue",
  "runner_state": {
    "scene_name": "prologue",
    "index": 12,
    "resume_mode": "say_wait"
  },
  "persistent_state": {
    "route": "A",
    "met_epsilon": true,
    "loop_count": 3
  }
}
```

说明：

- `runner_state` 用于恢复当前流程位置。
- `persistent_state` 会在读档时同步恢复。

### 14.3 运行时入口

- 在 `GameView` 激活时按 `S` 打开存档界面（见 `window.py` 事件过滤逻辑）。
- 在存档界面里可执行保存与读取。

## 15. 持久化变量（persistent_state）

`persistent_state` 是跨场景共享、且会进入存档的字典，挂在 `ScriptRunner.persistent_state`。

脚本 API（`src/engine/script/api.py`）：

- `persistent_set(key, value)`
- `persistent_update(values)`
- `persistent_delete(key)`
- `persistent_clear()`

这些节点都属于即时节点：执行完会直接进入下一节点。

### 15.1 脚本示例

```python
from src.engine.script.api import call, persistent_set, persistent_update, say


def _log_route(runner):
    route = runner.persistent_state.get("route", "unknown")
    runner._run_terminal_write_node({"text": f"[route]={route}", "end": "\n"})


def build_scene():
    yield persistent_set("met_epsilon", True)
    yield persistent_update({"route": "A", "loop_count": 1})
    yield say("System", "已写入持久化变量。")
    yield call(_log_route)
```

### 15.2 在 callback 中读取并分支

```python
from src.engine.script.api import call


def _branch(runner):
    if runner.persistent_state.get("met_epsilon"):
        runner.jump("Ch1/loop1")


def build_scene():
    yield call(_branch)
```

## 16. `above_web` 说明（图片/额外文本框）

`image_*` 与 `textbox_*` 系列节点都支持 `above_web`（别名：`overlay` / `on_top` / `topmost`）。

- `above_web=False`（默认）：渲染在 Web 对话层下方。
- `above_web=True`：渲染在 Web 对话层上方，适合遮罩、前景特效、覆盖层提示。

示例：

```python
from src.engine.script.api import image_show, textbox_show


def build_scene():
    yield image_show("mask", above_web=True, opacity=0.75, duration_ms=150)
    yield textbox_show("hint", above_web=True, text="顶部提示", opacity=1.0)
```
