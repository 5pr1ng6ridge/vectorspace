"""场景管理器。"""

from __future__ import annotations

import re
from typing import Any, Callable

from .script.loader import load_scene_script
from .script.runner import ScriptRunner
from .ui.game_view import GameView


class SceneManager:
    def __init__(
        self,
        view: GameView,
        history_logger: Callable[[str], None] | None = None,
        terminal_logger: Callable[[str], None] | None = None,
        close_game_callback: Callable[[bool], None] | None = None,
    ) -> None:
        self.view = view
        self.current_runner: ScriptRunner | None = None
        self._history_logger = history_logger
        self._terminal_logger = terminal_logger
        self._close_game_callback = close_game_callback

    def load_scene(
        self,
        scene_name: str,
        on_loaded: Callable[[], None] | None = None,
    ) -> None:
        """按场景名加载并启动 Python 场景脚本。"""
        script_data = load_scene_script(scene_name)

        previous_runner = self.current_runner
        if previous_runner is not None:
            previous_runner.dispose()

        # 切场景前先清空上一场景残留文本，并播放 noise_* 过渡一轮。
        self.view.clear_dialogue_content()
        self.view.play_scene_noise_once()

        runner = ScriptRunner(
            self.view,
            script_data,
            on_jump=self.load_scene,
            on_node=self._on_runner_node,
            on_terminal_write=self._terminal_logger,
            on_close_game=self._close_game_callback,
        )
        self.current_runner = runner

        def _start_runner_after_noise() -> None:
            # 若期间又切了场景，旧 runner 不应再启动。
            if self.current_runner is not runner:
                return
            runner.start()

        # noise 播放期间不启动新场景，仅清空残留；播放结束后再开始执行节点。
        self.view.play_scene_noise_once(on_finished=_start_runner_after_noise)

        if on_loaded is not None:
            try:
                on_loaded()
            except Exception as exc:
                print(f"[SceneManager] on_loaded failed: {exc}")

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
        text = self._strip_tags(raw_text if isinstance(raw_text, str) else str(raw_text))
        if speaker:
            self._log_history(f"[{speaker}]: {text}")
            return
        self._log_history(text)

    def _log_history(self, text: str) -> None:
        if self._history_logger is None:
            return
        payload = text.rstrip("\n") + "\n\n"
        try:
            self._history_logger(payload)
        except Exception as exc:
            print(f"[SceneManager] history log failed: {exc}")

    @staticmethod
    def _strip_tags(text: str) -> str:
        text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()
