"""场景调度器。

职责:
1. 根据场景名加载 JSON 脚本。
2. 创建并启动 ``ScriptRunner``。
"""

from .resources.paths import script_path
from .script.loader import load_scene_script
from .script.runner import ScriptRunner
from .ui.game_view import GameView

class SceneManager:
    def __init__(self, view: GameView) -> None:
        self.view = view
        self.current_runner: ScriptRunner | None = None

    def load_scene(self, scene_name: str) -> None:
        """加载并播放指定场景。"""
        path = script_path("scenes", f"{scene_name}.json")
        script_data = load_scene_script(path)
        self.current_runner = ScriptRunner(self.view, script_data)
        self.current_runner.start()
