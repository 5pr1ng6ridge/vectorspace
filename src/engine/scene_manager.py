"""场景管理器。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .script.loader import load_scene_script
from .script.runner import ScriptRunner
from .ui.dialogue_text import dialogue_to_plain_text
from .ui.game_view import GameView


class SceneManager:
    def __init__(
        self,
        view: GameView,
        history_logger: Callable[[str], None] | None = None,
        terminal_logger: Callable[[str], None] | None = None,
        close_game_callback: Callable[[bool], None] | None = None,
        scene_changed_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.view = view
        self.current_runner: ScriptRunner | None = None
        self.current_scene_name: str | None = None
        self.persistent_state: dict[str, Any] = {}
        self._history_logger = history_logger
        self._terminal_logger = terminal_logger
        self._close_game_callback = close_game_callback
        self._scene_changed_callback = scene_changed_callback

    def load_scene(
        self,
        scene_name: str,
        on_loaded: Callable[[], None] | None = None,
        restore_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """按场景名加载并启动 Python 场景脚本。"""
        script_data = load_scene_script(scene_name)
        resolved_scene_name = str(script_data.get("id", scene_name)).strip() or scene_name
        self.current_scene_name = resolved_scene_name

        if self._scene_changed_callback is not None:
            try:
                self._scene_changed_callback(resolved_scene_name)
            except Exception as exc:
                print(f"[SceneManager] scene_changed callback failed: {exc}")

        previous_runner = self.current_runner
        if previous_runner is not None:
            previous_runner.dispose()

        # 切场景前先清空上一场景残留文本，再播放一次 noise 过渡。
        self.view.clear_dialogue_content()

        runner = ScriptRunner(
            self.view,
            script_data,
            on_jump=self.load_scene,
            on_node=self._on_runner_node,
            on_terminal_write=self._terminal_logger,
            on_close_game=self._close_game_callback,
            persistent_state=self.persistent_state,
        )
        self.current_runner = runner

        def _start_runner_after_noise() -> None:
            if self.current_runner is not runner:
                return
            if restore_snapshot is not None:
                runner.restore_from_snapshot(restore_snapshot)
                return
            runner.start()

        # noise 播放期间只清理旧内容，不启动新场景；播放结束后再开始执行节点。
        self.view.play_scene_noise_once(on_finished=_start_runner_after_noise)

        if on_loaded is not None:
            try:
                on_loaded()
            except Exception as exc:
                print(f"[SceneManager] on_loaded failed: {exc}")

    def create_save_payload(self) -> dict[str, Any] | None:
        if self.current_runner is None or self.current_scene_name is None:
            return None

        return {
            "scene_name": self.current_scene_name,
            "runner_state": self.current_runner.snapshot_state(),
            "persistent_state": deepcopy(self.persistent_state),
        }

    def load_save_payload(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False

        scene_name = str(payload.get("scene_name") or "").strip()
        runner_state = payload.get("runner_state")
        persistent_state = payload.get("persistent_state", {})
        if not scene_name or not isinstance(runner_state, dict):
            return False

        self.persistent_state.clear()
        if isinstance(persistent_state, dict):
            self.persistent_state.update(deepcopy(persistent_state))

        self.load_scene(scene_name, restore_snapshot=runner_state)
        return True

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
        text = dialogue_to_plain_text(
            raw_text if isinstance(raw_text, str) else str(raw_text)
        ).strip()
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
