# VECTSPACE 协作开发说明（中文）

## 1. 项目结构

- `src/engine/app.py`: 应用入口，初始化资源根目录和默认字体。
- `src/engine/window.py`: 主窗口装配 `GameView` 与 `SceneManager`。
- `src/engine/scene_manager.py`: 根据场景名加载脚本并启动执行器。
- `src/engine/script/loader.py`: 读取 JSON 脚本。
- `src/engine/script/runner.py`: 核心流程执行（节点调度、打字机、样式与速度）。
- `src/engine/ui/game_view.py`: 画面层与点击推进事件。
- `src/engine/ui/dialogue_text.py`: Web 对话渲染（KaTeX、动画标签、复制拦截）。
- `game/scripts/scenes/*.json`: 场景脚本。
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
