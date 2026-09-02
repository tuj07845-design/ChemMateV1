# -*- coding: utf-8 -*-
"""Mock Tool 集——接口与未来真实 Tool 完全一致（见 base.py）。

替换真实 Tool 时只改 agent/mock_agent.py 的 TOOL_REGISTRY，
本目录与 UI、server 均不需改动。
"""

from .base import ToolBase, ToolError, ToolResult, ToolStopped  # noqa: F401
from .mock_path_finder import MockPathFinderTool  # noqa: F401
from .mock_data_get import MockDataGetTool  # noqa: F401
from .mock_draw_mat import MockDrawMatTool  # noqa: F401
from .mock_word_create import MockWordCreateTool  # noqa: F401
