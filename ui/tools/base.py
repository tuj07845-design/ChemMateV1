# -*- coding: utf-8 -*-
"""Tool 接口约定层。

UI 只认这里的接口。以后接真实 Tool 时：
    1. 写一个 RealXxxTool(ToolBase)，实现 execute()，返回 ToolResult；
    2. 在 agent/mock_agent.py 的 TOOL_REGISTRY 里把 Mock 换成 Real；
    3. UI 与 server 一行都不用改。

约定：
    execute(task, context, log, stop)
        task     用户任务原文
        context  跨 Tool 共享的可写 dict（如 data_get 写入 stream 数据，
                 word_create 读取它生成报告）
        log      日志回调 log(source, text, ok=None)，source 形如 "Tool: path_finder"
        stop     threading.Event，被置位时 Tool 应尽快抛 ToolStopped 终止
"""

from __future__ import annotations

import threading
from typing import Any, Callable


class ToolError(Exception):
    """Tool 执行失败。message 会展示在卡片与控制台。"""


class ToolStopped(Exception):
    """用户点了[停止]，Tool 主动终止。"""


class ToolResult(dict):
    """统一返回结构。

    success  bool
    message  str   一句话结果，显示在 workflow 卡片上
    data     dict  结构化数据（data_get 的股流数据等），写入 context 供后续 Tool 用
    """

    def __init__(self, success: bool, message: str = "", data: dict | None = None):
        super().__init__(success=success, message=message, data=data or {})


LogFn = Callable[[str, str, bool | None], None]


class ToolBase:
    """所有 Tool（Mock 与未来真实 Tool）的基类。"""

    name: str = "tool"            # 注册名（与 Agent 工具名一致）
    display_name: str = "Tool"    # 卡片上的英文名
    cn_name: str = "工具"          # 卡片上的中文名
    description: str = ""

    def execute(
        self,
        task: str,
        context: dict[str, Any],
        log: LogFn,
        stop: threading.Event,
    ) -> ToolResult:
        raise NotImplementedError
