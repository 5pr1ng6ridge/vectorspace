from __future__ import annotations

from typing import Callable, Dict, List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import (
    QFontDatabase,
    QFont,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPlainTextEdit,
    QLineEdit
)

from ..resources.paths import asset_path


class TerminalView(QWidget):
    # 外部可以连这个信号来切到 GameView
    startGameRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # ===== UI 基本结构 =====
        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setUndoRedoEnabled(False)
        self.output.setFrameShape(QPlainTextEdit.NoFrame)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.input = TerminalInput(self)
        self.input.returnPressed.connect(self._on_return_pressed)
        self.input.historyUpRequested.connect(self._on_history_up)
        self.input.historyDownRequested.connect(self._on_history_down)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(self.output, 1)
        layout.addWidget(self.input, 0)

        # ===== 状态 =====
        self._history: List[str] = []
        self._history_index: int = 0

        # 命令分发器：命令名 -> 处理函数
        self._commands: Dict[str, Callable[[List[str]], None]] = {}
        self._register_commands()

        self._apply_style()
        self._boot_text()

    def _apply_style(self) -> None:
        font = self._load_pixel_font(28)

        self.output.setFont(font)
        self.input.setFont(font)

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
        self.print_line("VECTSPACE Terminal v0.1")
        self.print_line("Type 'help' for available commands.")
        self.print_line("")

    # ------------------------------------------------------------------
    # 基础输出
    # ------------------------------------------------------------------
    def print_line(self, text: str = "") -> None:
        """在终端末尾追加一行。"""
        self.output.appendPlainText(text)
        self._scroll_to_bottom()

    def print_block(self, text: str) -> None:
        """按行输出一个多行字符串。"""
        for line in text.splitlines():
            self.output.appendPlainText(line)
        if text.endswith("\n"):
            self.output.appendPlainText("")
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _replace_last_line(self, text: str) -> None:
        """用 text 替换掉最后一行（用于进度条、loading...）。"""
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    # ------------------------------------------------------------------
    # 输入 & 命令历史
    # ------------------------------------------------------------------
    def _on_return_pressed(self) -> None:
        raw = self.input.text()
        command = raw.strip()

        # 打印一行提示符 + 输入
        prompt = f"[vectspace@system ~]$ {raw}" if raw else "[vectspace@system ~]$"
        self.print_line(prompt)

        if command:
            self._history.append(command)
            self._history_index = len(self._history)

        self.input.clear()

        if command:
            self._execute_command(command)

    def _on_history_up(self) -> None:
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
        cmd = self._history[self._history_index]
        self.input.setText(cmd)
        self.input.setCursorPosition(len(cmd))

    def _on_history_down(self) -> None:
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            cmd = self._history[self._history_index]
        else:
            # 超过历史最后一条 -> 清空输入框
            self._history_index = len(self._history)
            cmd = ""
        self.input.setText(cmd)
        self.input.setCursorPosition(len(cmd))

    # ------------------------------------------------------------------
    # 命令分发器
    # ------------------------------------------------------------------
    def _register_commands(self) -> None:
        self._commands = {
            "help": self._cmd_help,
            "start": self._cmd_start,
            "t": self._cmd_test,
            "clear": self._cmd_clear,
            "echo": self._cmd_echo,
            "boot": self._cmd_boot_demo,   # 做个读取动画演示
        }

    def _execute_command(self, command: str) -> None:
        parts = command.split()
        if not parts:
            return
        name = parts[0].lower()
        args = parts[1:]

        handler = self._commands.get(name)
        if handler is None:
            self.print_line(f"Unknown command: {name}")
            return
        handler(args)

    # ------------------------------------------------------------------
    # 各个命令的实现
    # ------------------------------------------------------------------
    def _cmd_help(self, args: list[str]) -> None:
        self.print_block(
            "Available commands:\n"
            "  help        - show this message\n"
            "  start       - enter the game\n"
            "  clear       - clear terminal output\n"
            "  echo TEXT   - print TEXT\n"
            "  boot        - demo loading sequence\n"
        )

    def _cmd_clear(self, args: list[str]) -> None:
        self.output.clear()

    def _cmd_echo(self, args: list[str]) -> None:
        self.print_line(" ".join(args))

    def _cmd_start(self, args: list[str]) -> None:
        self._run_loading_sequence(
            on_finished=lambda: self.startGameRequested.emit()
        )

    def _cmd_test(self, args: list[str]) -> None:
        self.startGameRequested.emit()

    def _cmd_boot_demo(self, args: list[str]) -> None:
        # 单纯演示用
        self._run_loading_sequence(on_finished=None)

    # ------------------------------------------------------------------
    # 读条 / loading 效果
    # ------------------------------------------------------------------
    def _run_loading_sequence(self, on_finished: Callable[[], None] | None) -> None:
        """
        一个组合 demo：
          1) 输出几行“准备中”日志
          2) 显示一个 0% → 100% 的进度条
          3) 最后一行为 Loading... 小点点动画
        """
        self.print_line("Initializing math engine...")
        self.print_line("Scanning proof archives...")
        self.print_line("Allocating Hilbert space...")
        self.print_line("")  # 空行

        # 先输出一行初始进度
        base_text = "Loading resources"
        self.print_line(f"{base_text} 0%")

        # 进度条配置
        total_steps = 20
        interval_ms = 80
        current_step = 0

        def progress_tick() -> None:
            nonlocal current_step
            current_step += 1
            if current_step > total_steps:
                # 进度完成后，开始小点点动画
                self._replace_last_line(f"{base_text} 100%")
                self._run_dots_line(
                    prefix="Ready",
                    cycles=3,
                    interval_ms=300,
                    on_finished=on_finished,
                )
                return

            percent = int(current_step * 100 / total_steps)
            self._replace_last_line(f"{base_text} {percent}%")

            QTimer.singleShot(interval_ms, progress_tick)

        QTimer.singleShot(interval_ms, progress_tick)

    def _run_dots_line(
        self,
        prefix: str = "Loading",
        cycles: int = 3,
        interval_ms: int = 300,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """
        在最后一行做 prefix., prefix.., prefix... 的循环动画。
        cycles: 循环多少次（每个 cycle 是 "", ".", "..", "..." 这一串）
        """
        states = ["", ".", "..", "..."]
        total_ticks = cycles * len(states)
        tick_index = 0

        # 先输出一行基础文本
        self.print_line(f"{prefix}")

        def tick() -> None:
            nonlocal tick_index
            if tick_index >= total_ticks:
                # 动画结束
                self._replace_last_line(f"{prefix}...")
                if on_finished is not None:
                    on_finished()
                return

            state = states[tick_index % len(states)]
            self._replace_last_line(f"{prefix}{state}")
            tick_index += 1
            QTimer.singleShot(interval_ms, tick)

        QTimer.singleShot(interval_ms, tick)
        
class TerminalInput(QLineEdit):
    historyUpRequested = Signal()
    historyDownRequested = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.historyUpRequested.emit()
            return
        if event.key() == Qt.Key_Down:
            self.historyDownRequested.emit()
            return
        super().keyPressEvent(event)