from __future__ import annotations

from typing import Callable, Dict, List, Optional, Union, Deque
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt, Signal, QTimer
from PySide6.QtGui import (
    QInputMethodEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QKeySequence,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit

from .crt_text_edit import CrtTextEdit




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



class TerminalView(CrtTextEdit):
    """
    Terminal-like控件：
      - 输出和输入都在同一个区域
      - 底部一行有 prompt，比如 'vectspace> '
      - 输入回车执行命令
      - ↑/↓ 翻历史
      - 支持读条动画
    """
    startGameRequested = Signal(str)
    collapseRequested = Signal()
    CURSOR_BLINK_INTERVAL_MS = 530
    CURSOR_HEIGHT_RATIO = 0.2
    CURSOR_MIN_HEIGHT_PX = 2
    ENABLE_FULLSCREEN_POSTPROCESS = True

    def __init__(self, parent=None, *, history_mode: bool = False) -> None:
        super().__init__(parent)
        self._history_mode = bool(history_mode)

        # 样式
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._prompt: str = "[VECTSPACE@system: ~]$ "
        self._input_start_pos: int = 0  # 当前输入行的开始位置（在整个文本中的下标）
        self._terminal_cursor_pos: int = 0
        self._accept_input: bool = not self._history_mode
        self._collapse_on_down_enabled = False
        self._cursor_blink_visible = True
        self._cursor_blink_timer = QTimer(self)
        self._cursor_blink_timer.setInterval(self.CURSOR_BLINK_INTERVAL_MS)
        self._cursor_blink_timer.timeout.connect(self._toggle_cursor_blink)

        # 历史
        self._history: List[str] = []
        self._history_index: int = 0

        # 命令表
        self._commands: Dict[str, Callable[[List[str]], bool]] = {}
        self._register_commands()
        
        self._step_queue: Deque[TerminalStep] = deque()
        self._queue_running: bool = False
        
        self._apply_style()
        if not self._history_mode:
            self._cursor_blink_timer.start()
        if self._history_mode:
            self.setReadOnly(True)
            self.print_block("[ScriptHistory] ready.")
        else:
            self._boot_text()
        
        
        
        
    def _apply_style(self) -> None:
        self.apply_crt_style(24)

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
        self._sync_terminal_cursor_from_editor()
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
        self._set_terminal_cursor_position(self._input_start_pos)
        self._scroll_to_bottom()

    def _current_input_text(self) -> str:
        """取出当前 prompt 之后的输入内容。"""
        full = self.toPlainText()
        if self._input_start_pos >= len(full):
            return ""
        return full[self._input_start_pos:].rstrip("\n")

    def _move_cursor_to_input_end(self) -> None:
        """把光标钉在当前输入区末尾。"""
        position = max(self._input_start_pos, self.document().characterCount() - 1)
        self._set_terminal_cursor_position(position)

    def _append_newline_at_end(self) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)
        cursor.insertText("\n")
        self._sync_terminal_cursor_from_editor()
        self._scroll_to_bottom()

    def _finish_terminal_sequence(self) -> None:
        self._accept_input = True
        self._insert_prompt()

    def _jump_to_gameview(self, scene_name: str | None = None) -> None:
        target = scene_name.strip() if isinstance(scene_name, str) else ""
        self.startGameRequested.emit(target)

    def append_history(self, text: str) -> None:
        if not isinstance(text, str):
            text = str(text)
        self.print_block(text)

    def ensure_input_mode(self, *, append_prompt: bool = True) -> None:
        """将终端切回可输入状态，可选地在末尾追加 prompt。"""
        if self._history_mode:
            return

        self._accept_input = True
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.setTextCursor(cursor)

        if append_prompt:
            plain_text = self.toPlainText()
            last_line = plain_text.rsplit("\n", 1)[-1] if plain_text else ""
            if last_line != self._prompt:
                if plain_text and not plain_text.endswith("\n"):
                    cursor.insertText("\n")
                cursor.insertText(self._prompt)
                self._input_start_pos = cursor.position()
            else:
                self._input_start_pos = len(plain_text)
        else:
            self._input_start_pos = cursor.position()

        self._move_cursor_to_input_end()
        self.setFocus(Qt.OtherFocusReason)

    def set_collapse_on_down_enabled(self, enabled: bool) -> None:
        self._collapse_on_down_enabled = bool(enabled)
    
    # ---------------- 键盘事件重写：实现终端行为 ----------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._history_mode:
            return super().keyPressEvent(event)

        key = event.key()
        if (
            self._collapse_on_down_enabled
            and key == Qt.Key_Escape
            and event.modifiers() == Qt.NoModifier
        ):
            self.collapseRequested.emit()
            return

        if event.matches(QKeySequence.Copy):
            self.copy()
            return
        if event.matches(QKeySequence.SelectAll):
            self.selectAll()
            return
        if event.matches(QKeySequence.Cut):
            return

        if not self._accept_input:
            # 读条时禁用输入编辑，但保留复制等只读操作
            if event.matches(QKeySequence.Copy) or event.matches(QKeySequence.SelectAll):
                return super().keyPressEvent(event)
            return

        cursor = self.textCursor()
        self.setTextCursor(cursor)
        if cursor.hasSelection():
            self._restore_editor_cursor()
            cursor = self.textCursor()
        elif cursor.position() < self._input_start_pos:
            self._restore_editor_cursor()
            cursor = self.textCursor()
        is_editing_input = (
            key in (Qt.Key_Backspace, Qt.Key_Delete)
            or event.matches(QKeySequence.Paste)
            or bool(event.text())
        )
        if cursor.hasSelection() and is_editing_input:
            # 有选区时，编辑动作不允许覆盖选中文本（尤其是历史输出区域）
            # 统一把光标收回到当前输入末尾，再按普通输入逻辑处理。
            self._move_cursor_to_input_end()

        # ↑ / ↓ 历史
        if key == Qt.Key_Up:
            self._history_prev()
            return
        if key == Qt.Key_Down:
            self._history_next()
            return

        # Home：跳到输入起点
        if key == Qt.Key_Home:
            self._set_terminal_cursor_position(self._input_start_pos)
            return

        # Backspace：不允许删到 prompt 左边
        if key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.position() <= self._input_start_pos:
                return
            super().keyPressEvent(event)
            self._sync_terminal_cursor_from_editor()
            return

        # Delete：不允许删到 prompt 左边
        if key == Qt.Key_Delete:
            cursor = self.textCursor()
            if cursor.position() < self._input_start_pos:
                return
            super().keyPressEvent(event)
            self._sync_terminal_cursor_from_editor()
            return

        # Left：不允许左移越过 prompt
        if key == Qt.Key_Left:
            cursor = self.textCursor()
            if cursor.position() <= self._input_start_pos:
                return
            super().keyPressEvent(event)
            self._sync_terminal_cursor_from_editor()
            return

        if key == Qt.Key_Right:
            super().keyPressEvent(event)
            self._sync_terminal_cursor_from_editor()
            return

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

        # 粘贴和普通输入统一钉到输入区，防止改写历史输出
        if (
            event.matches(QKeySequence.Paste)
            or (event.text() and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier)))
        ):
            cursor = self.textCursor()
            if cursor.position() < self._input_start_pos:
                self._move_cursor_to_input_end()

        # 其他按键：正常处理（文本输入）
        super().keyPressEvent(event)
        self._sync_terminal_cursor_from_editor()

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        # 中文输入法等组合输入走这个事件，不走普通 keyPressEvent。
        # 若当前有选区，IME 提交时会替换选区文本，这里统一收回到输入末尾。
        if self._history_mode or not self._accept_input:
            event.ignore()
            return

        cursor = self.textCursor()
        if cursor.hasSelection() or cursor.position() < self._input_start_pos:
            self._restore_editor_cursor()

        super().inputMethodEvent(event)

        # 兜底：IME 提交后若光标异常，再次拉回输入区
        cursor = self.textCursor()
        if cursor.position() < self._input_start_pos:
            self._restore_editor_cursor()
        else:
            self._sync_terminal_cursor_from_editor()

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
        self._sync_terminal_cursor_from_editor()
        self._scroll_to_bottom()

    def _clamp_terminal_cursor_pos(self, position: int) -> int:
        max_position = max(0, self.document().characterCount() - 1)
        return max(self._input_start_pos, min(int(position), max_position))

    def _set_terminal_cursor_position(self, position: int) -> None:
        previous_position = self._terminal_cursor_pos
        clamped_position = self._clamp_terminal_cursor_pos(position)
        self._terminal_cursor_pos = clamped_position
        cursor = self.textCursor()
        cursor.setPosition(clamped_position)
        self.setTextCursor(cursor)
        self._reset_cursor_blink()
        self._update_cursor_overlay(previous_position)

    def _restore_editor_cursor(self) -> None:
        self._set_terminal_cursor_position(self._terminal_cursor_pos)

    def _sync_terminal_cursor_from_editor(self) -> None:
        previous_position = self._terminal_cursor_pos
        self._terminal_cursor_pos = self._clamp_terminal_cursor_pos(
            self.textCursor().position()
        )
        self._reset_cursor_blink()
        self._update_cursor_overlay(previous_position)

    def _toggle_cursor_blink(self) -> None:
        self._cursor_blink_visible = not self._cursor_blink_visible
        self._update_cursor_overlay()

    def _reset_cursor_blink(self) -> None:
        self._cursor_blink_visible = True
        if not self._history_mode:
            self._cursor_blink_timer.start()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._reset_cursor_blink()
        self._update_cursor_overlay()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._cursor_blink_visible = False
        self._update_cursor_overlay()

    def _cursor_block_rect(self, position: int | None = None) -> QRect:
        cursor_position = self._clamp_terminal_cursor_pos(
            self._terminal_cursor_pos if position is None else position
        )
        cursor = QTextCursor(self.document())
        cursor.setPosition(cursor_position)
        cursor_rect = self.cursorRect(cursor)

        plain_text = self.toPlainText()
        current_char = ""
        if cursor_position < len(plain_text):
            current_char = plain_text[cursor_position]
        cell_sample = current_char if current_char not in ("\n", "\r", "") else "M"
        cell_width = max(1, self.fontMetrics().horizontalAdvance(cell_sample))
        cursor_height = max(
            self.CURSOR_MIN_HEIGHT_PX,
            int(round(cursor_rect.height() * self.CURSOR_HEIGHT_RATIO)),
        )

        block_rect = QRect(cursor_rect)
        block_rect.setWidth(cell_width)
        block_rect.setTop(block_rect.bottom() - cursor_height + 1)
        return block_rect

    def _cursor_dirty_rect(self, position: int | None = None) -> QRect:
        return self._cursor_block_rect(position).adjusted(-2, -2, 2, 2)

    def _update_cursor_overlay(self, previous_position: int | None = None) -> None:
        if self.is_fullscreen_postprocess_active():
            self.viewport().update()
            return

        dirty_rect = self._cursor_dirty_rect()
        if previous_position is not None:
            dirty_rect = dirty_rect.united(self._cursor_dirty_rect(previous_position))
        self.viewport().update(dirty_rect)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if (
            self._history_mode
            or not self._accept_input
            or not self.hasFocus()
            or not self._cursor_blink_visible
        ):
            return

        cursor_position = self._clamp_terminal_cursor_pos(self._terminal_cursor_pos)
        block_rect = self._cursor_block_rect(cursor_position).intersected(
            self.viewport().rect()
        )
        if block_rect.isEmpty():
            return

        painter = QPainter(self.viewport())
        painter.fillRect(block_rect, self.palette().text().color())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        self._update_cursor_overlay()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        self._update_cursor_overlay()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        self._update_cursor_overlay()

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
            "t1": self._cmd_test,
            "t2": self._cmd_test2,
            "c": self._cmd_continue,
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
            "  start [SCENE] - enter the game (optionally with target scene)\n"
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
        target_scene = args[0].strip() if args else ""

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
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",10),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
            PrintLineStep("                                                        [ timeout ]\n",1),
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
            PrintLineStep("\n",10),
            PrintLineStep("Fatal: VECTSPACE not responding\n",150),
            #CallbackStep(self._finish_terminal_sequence, 10),
            CallbackStep(lambda: self._jump_to_gameview(target_scene)),
        ]

        self.enqueue_steps(steps)
        return False
    
    def _cmd_continue(self, args: list[str]) -> bool:
        self._accept_input = False

        steps = [
            CallbackStep(lambda: self._jump_to_gameview(""))
        ]

        self.enqueue_steps(steps)
        return False
    
    def _cmd_test(self, args: list[str]) -> bool:
        self._accept_input = False
        target_scene = args[0].strip() if args else ""

        steps = [
            CallbackStep(lambda: self._jump_to_gameview("prologue"))
        ]

        self.enqueue_steps(steps)
        return False
 
    def _cmd_test2(self, args: list[str]) -> bool:
        self._accept_input = False
        target_scene = args[0].strip() if args else ""

        steps = [
            CallbackStep(lambda: self._jump_to_gameview("Ch1/loop1"))
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
