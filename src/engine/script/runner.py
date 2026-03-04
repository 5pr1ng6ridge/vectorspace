# src/engine/script/runner.py
from typing import Any
from PySide6.QtCore import QTimer
from ..ui.game_view import GameView

class ScriptRunner:
    def __init__(self, view: GameView, script_data: dict[str, Any]) -> None:
        self.view = view
        self.script_data = script_data
        self.flow: list[str] = script_data.get("flow", [])
        self.nodes: dict[str, dict[str, Any]] = script_data.get("nodes", {})
        self.index: int = 0

    def start(self) -> None:
        self.index = 0
        self._run_next()

    def _run_next(self) -> None:
        if self.index >= len(self.flow):
            # TODO: 场景结束，可以通知 SceneManager 做别的事
            self.view.set_dialogue_text("(场景结束)")
            return

        node_id = self.flow[self.index]
        node = self.nodes.get(node_id, {})
        node_type = node.get("type")

        if node_type == "say":
            text = node.get("text", "")
            # 暂时直接显示文本
            self.view.set_dialogue_text(text)

            # 模拟“按一下继续”：这里先自动过场，500ms 后跳到下一句
            self.index += 1
            QTimer.singleShot(500, self._run_next)

        else:
            # 未知节点类型：跳过
            self.index += 1
            self._run_next()