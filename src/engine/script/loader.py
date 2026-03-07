"""脚本加载器。"""

import json
from pathlib import Path
from typing import Any

def load_scene_script(path: Path) -> dict[str, Any]:
    """读取并解析场景 JSON。

    返回值约定:
    - ``nodes``: 节点字典
    - ``flow``: 节点播放顺序
    - ``defaults``: 可选默认参数（例如样式、打字速度）
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
