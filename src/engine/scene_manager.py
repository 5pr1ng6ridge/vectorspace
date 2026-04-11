"""Scene manager."""

from .script.loader import load_scene_script
from .script.runner import ScriptRunner
from .ui.game_view import GameView


class SceneManager:
    def __init__(self, view: GameView) -> None:
        self.view = view
        self.current_runner: ScriptRunner | None = None

    def load_scene(self, scene_name: str) -> None:
        """Load and start a scene by name.

        Loader priority:
        1. ``game/scripts/scenes/<scene_name>.py``
        2. ``game/scripts/scenes/<scene_name>.json``
        """
        script_data = load_scene_script(scene_name)
        self.current_runner = ScriptRunner(self.view, script_data)
        self.current_runner.start()
