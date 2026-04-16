"""场景管理器。"""

from __future__ import annotations

from typing import Any, Callable

from .script.loader import load_scene_script
from .script.runner import ScriptRunner
from .ui.game_view import GameView


class SceneManager:
    def __init__(
        self,
        view: GameView,
        history_logger: Callable[[str], None] | None = None,
    ) -> None:
        self.view = view
        self.current_runner: ScriptRunner | None = None
        self._history_logger = history_logger

    def load_scene(self, scene_name: str) -> None:
        """按场景名加载并启动 Python 场景脚本。"""
        script_data = load_scene_script(scene_name)

        previous_runner = self.current_runner
        runner = ScriptRunner(
            self.view,
            script_data,
            on_jump=self.load_scene,
            on_node=self._on_runner_node,
        )
        self.current_runner = runner
        if previous_runner is not None:
            previous_runner.dispose()
        runner.start()

    def _on_runner_node(
        self,
        _node_id: str,
        node: dict[str, Any],
        _index: int,
    ) -> None:
        if str(node.get("type", "")).strip().lower() != "say":
            return

        speaker = str(node.get("speaker", "")).strip()
        raw_text = node.get("text", "")
        text = raw_text if isinstance(raw_text, str) else str(raw_text)
        if speaker:
            self._log_history(f"{speaker}: {text}"+"\n")
            return
        self._log_history(text)

    def _log_history(self, text: str) -> None:
        if self._history_logger is None:
            return
        try:
            self._history_logger(text)
        except Exception as exc:
            print(f"[SceneManager] history log failed: {exc}")
