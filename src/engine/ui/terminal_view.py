from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union, Deque
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFontDatabase,
    QFont,
    QTextCursor,
    QKeyEvent,
)
from PySide6.QtWidgets import QPlainTextEdit

from ..resources.paths import asset_path



@dataclass
class PrintLineStep:
    text: str
    delay_ms: int = 200


@dataclass
class ReplaceLastLineStep:
    text: str
    delay_ms: int = 200


@dataclass
class ProgressStep:
    prefix: str
    start: int = 0
    end: int = 100
    step: int = 10
    interval_ms: int = 80


@dataclass
class DotsStep:
    prefix: str
    cycles: int = 3
    interval_ms: int = 250


@dataclass
class CallbackStep:
    callback: Callable[[], None]
    delay_ms: int = 0
    
@dataclass
class TimedLine:
    text: str
    delay_ms: int = 300

TerminalStep = Union[
    PrintLineStep,
    ReplaceLastLineStep,
    ProgressStep,
    DotsStep,
    CallbackStep,
]



class TerminalView(QPlainTextEdit):
    """
    Terminal-like控件：
      - 输出和输入都在同一个区域
      - 底部一行有 prompt，比如 'vectspace> '
      - 输入回车执行命令
      - ↑/↓ 翻历史
      - 支持读条动画
    """
    startGameRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # 样式
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self._prompt: str = "[VECTSPACE@system: ~]$ "
        self._input_start_pos: int = 0  # 当前输入行的开始位置（在整个文本中的下标）
        self._accept_input: bool = True

        # 历史
        self._history: List[str] = []
        self._history_index: int = 0

        # 命令表
        self._commands: Dict[str, Callable[[List[str]], bool]] = {}
        self._register_commands()

        self._apply_style()
        self._boot_text()
        self._insert_prompt()
        
        
        self._step_queue: Deque[TerminalStep] = deque()
        self._queue_running: bool = False
        
    def _apply_style(self) -> None:
        font = self._load_pixel_font(28)
        self.setFont(font)

        self.setStyleSheet("""
            TerminalView {
                background-color: #101010;
            }
            QPlainTextEdit {
                background-color: #101010;
                color: #d8ffd8;
                border: 1px solid #2f2f2f;
                selection-background-color: #2d5a2d;
            }
            QLineEdit {
                background-color: #101010;
                color: #d8ffd8;
                border: 1px solid #4a4a4a;
                padding: 6px;
                selection-background-color: #2d5a2d;
            }
        """)

    def _load_pixel_font(self, size: int) -> QFont:
        font_path = asset_path("fonts", "FSEX302.ttf")
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return QFont(families[0], size)
        return QFont("monospace", size)

    def _boot_text(self) -> None:
        self.print_line("VECTSPACE Terminal v0.1\n")
        self.print_line("Type 'help' for available commands.\n")
        self.print_line("\n")

    # ---------------- 基础输出操作 ----------------

    def _scroll_to_bottom(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def print_line(self, text: str = "", wrap=False) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        if wrap == True:
            cursor.insertText(text + "\n")
        else:
            cursor.insertText(text)
        self._scroll_to_bottom()

    def print_block(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText(text)
        if not text.endswith("\n"):
            cursor.insertText("\n")
        self._scroll_to_bottom()
        
    def _replace_last_line(self, text: str) -> None:
        """只修改最后一行的内容，保留它后面的换行结构。"""
        doc = self.document()
        block = doc.lastBlock()
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.LineUnderCursor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    # ---------------- prompt & 输入区域 ----------------

    def _insert_prompt(self) -> None:
        """在末尾插入一行 prompt，并准备输入。"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText(self._prompt)
        # 记录输入起点（在整个文档中的位置）
        self._input_start_pos = cursor.position()
        self._scroll_to_bottom()

    def _current_input_text(self) -> str:
        """取出当前 prompt 之后的输入内容。"""
        full = self.toPlainText()
        if self._input_start_pos >= len(full):
            return ""
        return full[self._input_start_pos:].rstrip("\n")

    def _finish_terminal_sequence(self) -> None:
        self._accept_input = True
        self._insert_prompt()

    def _jump_to_gameview(self) -> None:
        self.startGameRequested.emit()
    
    # ---------------- 键盘事件重写：实现终端行为 ----------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._accept_input:
            # 读条时禁用输入（你喜欢也可以允许 Ctrl+C 之类的）
            return

        key = event.key()

        cursor = self.textCursor()
        self.setTextCursor(cursor)

        # ↑ / ↓ 历史
        if key == Qt.Key_Up:
            self._history_prev()
            return
        if key == Qt.Key_Down:
            self._history_next()
            return

        # Home：跳到输入起点
        if key == Qt.Key_Home:
            cursor = self.textCursor()
            cursor.setPosition(self._input_start_pos)
            self.setTextCursor(cursor)
            return

        # Backspace：不允许删到 prompt 左边
        if key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.position() <= self._input_start_pos:
                return
            return super().keyPressEvent(event)

        # Left：不允许左移越过 prompt
        if key == Qt.Key_Left:
            cursor = self.textCursor()
            if cursor.position() <= self._input_start_pos:
                return
            return super().keyPressEvent(event)

        # Enter：提交命令
        if key in (Qt.Key_Return, Qt.Key_Enter):
            command = self._current_input_text()
            # 先插入换行，让这一行固定下来
            super().keyPressEvent(event)

            # 存历史
            cmd_stripped = command.strip()
            if cmd_stripped:
                self._history.append(cmd_stripped)
                self._history_index = len(self._history)

            # 执行命令；根据返回值决定是否立刻追加一个新 prompt
            immediate_prompt = self._execute_command(cmd_stripped)
            if immediate_prompt:
                self._insert_prompt()
            return

        # 其他按键：正常处理（文本输入）
        super().keyPressEvent(event)

    # ---------------- 历史操作 ----------------

    def _history_prev(self) -> None:
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
        cmd = self._history[self._history_index]
        self._set_current_input(cmd)

    def _history_next(self) -> None:
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            cmd = self._history[self._history_index]
        else:
            self._history_index = len(self._history)
            cmd = ""
        self._set_current_input(cmd)

    def _set_current_input(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

        # 选中当前输入区域并替换
        cursor.setPosition(self._input_start_pos, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self._scroll_to_bottom()

    # ---------------- 命令分发器 ----------------

    def _register_commands(self) -> None:
        # handler(args) -> bool：返回 True 表示需要立即追加新 prompt
        self._commands = {
            "help": self._cmd_help,
            "start": self._cmd_start,
            "clear": self._cmd_clear,
            "echo": self._cmd_echo,
        }

    def _execute_command(self, command: str) -> bool:
        if not command:
            return True  # 空命令就直接再给一个 prompt

        parts = command.split()
        name = parts[0].lower()
        args = parts[1:]

        handler = self._commands.get(name)
        if handler is None:
            self.print_line(f"Unknown command: {name}"+"\n")
            return True

        return handler(args)

    # ====== 各命令实现：返回值决定要不要立即加 prompt ======

    def _cmd_help(self, args: List[str]) -> bool:
        self.print_block(
            "Available commands:\n"
            "  help        - show this message\n"
            "  start       - enter the game (with loading)\n"
            "  clear       - clear terminal output\n"
            "  echo TEXT   - print TEXT\n"
            "  boot        - demo loading sequence\n"
        )
        return True

    def _cmd_clear(self, args: List[str]) -> bool:
        self.clear()
        # 清空之后需要重新插入一行 prompt，由外面统一做
        return True

    def _cmd_echo(self, args: List[str]) -> bool:
        self.print_line(" ".join(args)+"\n")
        return True

    def _cmd_start(self, args: list[str]) -> bool:
        self._accept_input = False

        steps = [
            PrintLineStep("Initializing math engine...\n", 180),
            PrintLineStep("Scanning proof archives...\n", 220),
            PrintLineStep("Allocating Hilbert space...\n", 320),
            PrintLineStep("\n", 120),

            PrintLineStep("Loading resources 0%", 80),
            ProgressStep(
                prefix="Loading resources",
                start=0,
                end=100,
                step=5,
                interval_ms=70,
            ),
            PrintLineStep("\n", 10),

            PrintLineStep("Ready", 80),
            DotsStep(
                prefix="Ready",
                cycles=3,
                interval_ms=250,
            ),
            PrintLineStep("\n", 10),

            #CallbackStep(self._finish_terminal_sequence, 10),
            CallbackStep(self._jump_to_gameview),
        ]

        self.enqueue_steps(steps)
        return False
 
    # ---------------- 读条动画：xx% + Loading... ----------------

    def enqueue_steps(
        self,
        steps: list[TerminalStep],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        for step in steps:
            self._step_queue.append(step)

        if on_finished is not None:
            self._step_queue.append(CallbackStep(on_finished))

        if not self._queue_running:
            self._queue_running = True
            self._run_next_step()
            
    def _run_next_step(self) -> None:
        if not self._step_queue:
            self._queue_running = False
            return

        step = self._step_queue.popleft()

        if isinstance(step, PrintLineStep):
            self.print_line(step.text)
            QTimer.singleShot(step.delay_ms, self._run_next_step)
            return

        if isinstance(step, ReplaceLastLineStep):
            self._replace_last_line(step.text)
            QTimer.singleShot(step.delay_ms, self._run_next_step)
            return

        if isinstance(step, ProgressStep):
            self._run_progress_step(step, self._run_next_step)
            return

        if isinstance(step, DotsStep):
            self._run_dots_step(step, self._run_next_step)
            return

        if isinstance(step, CallbackStep):
            step.callback()
            QTimer.singleShot(step.delay_ms, self._run_next_step)
            return

        # 未知 step，跳过
        QTimer.singleShot(0, self._run_next_step)
        
    def _run_progress_step(
        self,
        step: ProgressStep,
        on_finished: Callable[[], None],
    ) -> None:
        current = step.start

        # 这里假定上一行已经存在，比如：
        # PrintLineStep("Loading resources 0%")
        # 然后 ProgressStep 负责不断替换它
        def tick() -> None:
            nonlocal current

            self._replace_last_line(f"{step.prefix} {current}%")

            if current >= step.end:
                on_finished()
                return

            current = min(current + step.step, step.end)
            QTimer.singleShot(step.interval_ms, tick)

        tick()
        
    def _run_dots_step(
        self,
        step: DotsStep,
        on_finished: Callable[[], None],
    ) -> None:
        states = ["", ".", "..", "..."]
        total_ticks = step.cycles * len(states)
        tick_index = 0

        # 同样假定上一行已经存在，或者你也可以这里先 print_line(step.prefix)
        def tick() -> None:
            nonlocal tick_index

            if tick_index >= total_ticks:
                self._replace_last_line(f"{step.prefix}...")
                on_finished()
                return

            suffix = states[tick_index % len(states)]
            self._replace_last_line(f"{step.prefix}{suffix}")
            tick_index += 1
            QTimer.singleShot(step.interval_ms, tick)

        tick()

    def _run_progress_step(
        self,
        step: ProgressStep,
        on_finished: Callable[[], None],
    ) -> None:
        current = step.start

        # 这里假定上一行已经存在，比如：
        # PrintLineStep("Loading resources 0%")
        # 然后 ProgressStep 负责不断替换它
        def tick() -> None:
            nonlocal current

            self._replace_last_line(f"{step.prefix} {current}%")

            if current >= step.end:
                on_finished()
                return

            current = min(current + step.step, step.end)
            QTimer.singleShot(step.interval_ms, tick)

        tick()
