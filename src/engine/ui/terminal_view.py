from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union, Deque
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFont,
    QTextCursor,
    QKeyEvent,
    QMouseEvent,
    QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit

from ..resources.fonts import load_font_family



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
    states: list
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

    def __init__(self, parent=None, *, history_mode: bool = False) -> None:
        super().__init__(parent)
        self._history_mode = bool(history_mode)

        # 样式
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAnywhere)

        self._prompt: str = "[VECTSPACE@system: ~]$ "
        self._input_start_pos: int = 0  # 当前输入行的开始位置（在整个文本中的下标）
        self._accept_input: bool = not self._history_mode

        # 历史
        self._history: List[str] = []
        self._history_index: int = 0

        # 命令表
        self._commands: Dict[str, Callable[[List[str]], bool]] = {}
        self._register_commands()
        
        self._step_queue: Deque[TerminalStep] = deque()
        self._queue_running: bool = False
        
        self._apply_style()
        if self._history_mode:
            self.setReadOnly(True)
            self.print_block("[ScriptHistory] ready.")
        else:
            self._boot_text()
        
        
        
        
    def _apply_style(self) -> None:
        font = self._load_pixel_font(19)
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
        primary_family = load_font_family("fonts", "FSEX302.ttf")
        fallback_family = load_font_family(
            "fonts",
            "fusion-pixel-12px-monospaced-zh_hans.ttf",
        )

        families: list[str] = []
        if primary_family:
            families.append(primary_family)
        if fallback_family and fallback_family not in families:
            families.append(fallback_family)

        if families:
            font = QFont()
            font.setPointSize(size)
            font.setFamilies(families)
            return font

        if fallback_family:
            return QFont(fallback_family, size)
        return QFont("monospace", size)

    def _boot_text(self) -> None:
        self._accept_input = False

        steps = [
            PrintLineStep("***********************************\n",15),
            PrintLineStep("*  Welcome to WORLD2VEC_TERMINAL  *\n",15),
            PrintLineStep("***********************************\n",50),
            PrintLineStep("world2vec Terminal v0.1\n"),
            PrintLineStep("Type 'help' for available commands.\n",250),
            PrintLineStep("\n"),
            CallbackStep(self._finish_terminal_sequence, 10),
            #CallbackStep(self._jump_to_gameview),
        ]

        self.enqueue_steps(steps)
        return False
        

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

    def _move_cursor_to_input_end(self) -> None:
        """把光标钉在当前输入区末尾。"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if cursor.position() < self._input_start_pos:
            cursor.setPosition(self._input_start_pos)
        self.setTextCursor(cursor)

    def _append_newline_at_end(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText("\n")
        self._scroll_to_bottom()

    def _finish_terminal_sequence(self) -> None:
        self._accept_input = True
        self._insert_prompt()

    def _jump_to_gameview(self) -> None:
        self.startGameRequested.emit()

    def append_history(self, text: str) -> None:
        if not isinstance(text, str):
            text = str(text)
        self.print_block(text)
    
    # ---------------- 键盘事件重写：实现终端行为 ----------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._history_mode:
            event.ignore()
            return
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
            # 终端回车总是提交整行，不在中间断开右侧文本
            self._move_cursor_to_input_end()
            command = self._current_input_text()
            # 先在末尾插入换行，让这一行固定下来
            self._append_newline_at_end()

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # 禁止鼠标点击改变光标位置（保留焦点）
        self.setFocus(Qt.MouseFocusReason)
        self._move_cursor_to_input_end()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.setFocus(Qt.MouseFocusReason)
        self._move_cursor_to_input_end()
        event.accept()

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
            "start": self._cmd_init,
            "boot": self._cmd_init,
            "init": self._cmd_init,
            "clear": self._cmd_clear,
            "echo": self._cmd_echo,
            "t": self._cmd_test,
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

    def _cmd_init(self, args: list[str]) -> bool:
        self._accept_input = False

        steps = [
            PrintLineStep("loading VECTSPACE...\n",50),
            PrintLineStep("    build by. . . . . . . . . . . . . . . . . . . . . .Epsilon\n",50),
            PrintLineStep("    fork from . . . . . . . . . . . . . . . . . . . . .\mathbb{R}\n",50),
            PrintLineStep("\n"),
            PrintLineStep("Connecting to VECTSPACE\n",100),
            PrintLineStep("  * Starting system...\n",50),
            PrintLineStep("  * Initializing CPU...\n",450),
            PrintLineStep("  * Initializing RAG...\n",250),
            PrintLineStep("  * Initializing OI...\n",100),
            PrintLineStep("  * Loading instances...\n",500),
            PrintLineStep("  * Verifying instances...\n",50),
            PrintLineStep("    0. E  . . . . . . . . . . . . . . . . . . . . . . . [ success ]\n",100),
            PrintLineStep("    1. E' . . . . . . . . . . . . . . . . . . . . . . . [ success ]\n",167),
            PrintLineStep("    2. D  . . . . . . . . . . . . . . . . . . . . . . . [         ]\n",100),
            PrintLineStep("  * Loading EGO...\n",450),
            PrintLineStep("    Login: E'\n",15),
            PrintLineStep("  * Loading architecture...                         \n",100),
            PrintLineStep("  * Loading virtual OI...\n",150),
            PrintLineStep("  * Loading skills...\n",100),
            PrintLineStep("  * Loading RAG...\n",250),
            PrintLineStep("  * Importing MEM...\n",555),
            PrintLineStep("    Warning: failed to structured MEM.\n",15),
            PrintLineStep("  * Resurrection MEM...                                 [ failed  ]\n",1000),
            PrintLineStep("                                                        [ failed  ]\n",1000),
            PrintLineStep("                                                        [ timeout ]\n",1000),
            PrintLineStep("  * Partitoning MEM...\n",500),
            PrintLineStep("  * Importing MEM...\n",1000),
            PrintLineStep("    Warning: low CPU usage\n",10),
            PrintLineStep("  * Visualizating VECTSPACE . . . . . . . . . . . . . . [ timeout ]\n",1000),
            PrintLineStep("                                                        [ timeout ]\n",1000),
            PrintLineStep("                                                        [ timeout ]\n",1000),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",100),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("  *\n",10),
            PrintLineStep("\n",2500),
            PrintLineStep("Fatal: VECTSPACE not responding\n"),
            #CallbackStep(self._finish_terminal_sequence, 10),
            CallbackStep(self._jump_to_gameview),
        ]

        self.enqueue_steps(steps)
        return False
    
    def _cmd_test(self, args: list[str]) -> bool:
        self._accept_input = False

        steps = [
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
        states = step.states
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
