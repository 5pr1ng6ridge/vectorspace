my-math-vn/
├─ main.py                 # 入口脚本（适合 PyInstaller 打包，从这里进）
├─ requirements.txt        # 依赖（PySide6 等）
├─ README.md
├─ src/
│  └─ engine/              # “通用引擎”代码（将来可以复用到别的游戏）
│     ├─ __init__.py
│     ├─ app.py            # 创建 QApplication，启动主窗口
│     ├─ window.py         # QMainWindow，管理主 UI
│     ├─ scene_manager.py  # 场景/脚本切换
│     ├─ state.py          # 游戏状态：变量、已读记录、存档
│     ├─ resources/
│     │  ├─ __init__.py
│     │  └─ paths.py       # 资源路径管理（适配打包后路径）
│     ├─ ui/               # 纯 UI 相关类
│     │  ├─ __init__.py
│     │  ├─ game_view.py   # 主游戏画面（背景+立绘+对话框等）
│     │  ├─ dialogue_box.py# 对话框控件
│     │  ├─ choice_menu.py # 选项菜单
│     │  └─ overlays.py    # 特效层、黑幕层等
│     ├─ script/           # 剧情脚本系统
│     │  ├─ __init__.py
│     │  ├─ loader.py      # 读取 JSON/YAML 脚本
│     │  ├─ runner.py      # 一条条执行脚本节点
│     │  └─ nodes.py       # 各种节点类型定义（say / choice / jump / effect / quiz 等）
│     ├─ gameplay/         # 各种玩法（题目、证明拼接等）
│     │  ├─ __init__.py
│     │  ├─ quiz.py        # 选择题/填空题逻辑
│     │  └─ proof.py       # 证明拼步骤玩法（之后慢慢写）
│     └─ latex/            # 以后搞公式渲染的地方
│        ├─ __init__.py
│        └─ renderer.py    # 提供: string -> QImage / QPixmap 的接口
│
├─ game/                   # “这款游戏”的内容（资源+脚本）
│  ├─ assets/
│  │  ├─ backgrounds/
│  │  ├─ characters/
│  │  ├─ ui/
│  │  ├─ fonts/
│  │  ├─ sfx/
│  │  └─ music/
│  └─ scripts/
│     ├─ scenes/           # 每个场景一个 JSON/YAML
│     │  └─ prologue.json
│     └─ config/
│        └─ game_config.json  # 游戏标题、窗口大小、默认字体等
└─ tests/                  # 将来要写测试的话可以用