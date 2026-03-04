# src/engine/script/runner.py
from typing import Any

from ..ui.game_view import GameView
from ..latex.renderer import render_latex_block


class ScriptRunner:
    """
    最小版脚本执行器：
      - 支持 say / formula
      - 按 flow 顺序播放
      - 每个节点等待一次点击
    """

    def __init__(self, view: GameView, script_data: dict[str, Any]) -> None:
        self.view = view
        self.script_data = script_data
        self.flow: list[str] = script_data.get("flow", [])
        self.nodes: dict[str, dict[str, Any]] = script_data.get("nodes", {})

        self.index: int = 0
        self.waiting_for_click: bool = False

        # 监听点击
        self.view.advanceRequested.connect(self._on_advance_requested)

    def start(self) -> None:
        self.index = 0
        self._show_current_node()

    # ====== 内部逻辑 ======

    def _show_current_node(self) -> None:
        if self.index >= len(self.flow):
            # 场景结束
            self.view.show_text("(场景结束，点击也不会再前进喵)")
            self.waiting_for_click = False
            return

        node_id = self.flow[self.index]
        node = self.nodes.get(node_id, {})
        node_type = node.get("type")

        if node_type == "say":
            speaker = node.get("speaker", "")
            text = node.get("text", "")

            # 新：单独设置姓名框和正文
            if speaker:
                self.view.set_name(speaker)
            else:
                self.view.set_name("")

            self.view.show_text(text)
            self.waiting_for_click = True

        elif node_type == "formula":
            # 公式节点可以选择清空 name 或保留上一句说话的人，看你演出需求
            self.view.set_name("")
            expr = node.get("latex", "")
            if not expr:
                self.view.show_text("(空公式节点)")
            else:
                pix = render_latex_block(expr)
                self.view.show_formula(pix)
            self.waiting_for_click = True
        
        elif node_type == "bg":
            # 背景切换节点
            filename = node.get("file", "")
            if filename:
                self.view.set_background(filename)
            self.index += 1
            self._show_current_node()
            return
        
        else:
            # 未知节点类型，直接跳过
            self.index += 1
            self._show_current_node()

    def _on_advance_requested(self) -> None:
        if not self.waiting_for_click:
            return

        self.waiting_for_click = False
        self.index += 1
        self._show_current_node()