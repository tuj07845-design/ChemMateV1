# -*- coding: utf-8 -*-
"""Mock path_finder —— 按文件名定位 Aspen 模型文件。

真实版对应 CMV1/path_finder_tool.py 的 path_finder(filename)，
返回结构保持一致（path / matches），将来直接替换。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .base import LogFn, ToolBase, ToolResult, ToolStopped

MOCK_MODEL_FILE = "10万吨环己烷.bkp"


class MockPathFinderTool(ToolBase):
    name = "path_finder"
    display_name = "path_finder"
    cn_name = "模型文件定位"
    description = "按文件名查找 Aspen 模型文件（.bkp/.apwz），返回绝对路径"

    def execute(
        self,
        task: str,
        context: dict[str, Any],
        log: LogFn,
        stop: threading.Event,
    ) -> ToolResult:
        log("Tool: path_finder", "Searching...")
        time.sleep(0.8)
        if stop.is_set():
            raise ToolStopped
        log("Tool: path_finder", f"✓ Found: {MOCK_MODEL_FILE}", ok=True)
        time.sleep(0.4)

        path = rf"C:\Users\Fool\Desktop\ChemMateV1工作台\{MOCK_MODEL_FILE}"
        return ToolResult(
            success=True,
            message=f"✓ {MOCK_MODEL_FILE}",
            data={"model_file": MOCK_MODEL_FILE, "model_path": path},
        )
