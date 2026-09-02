# -*- coding: utf-8 -*-
"""
ChemMate V1 — 流程数据 / 绘图入口的进程级包装

作用：
  - 把 draw_mat 与 data_get 的数据缓存（_LAST_PROCESS_DATA）
    组合成"画图工具"这一侧的统一对外面：
      wrap_data_get   包 data_get，返回值自动进缓存
      wrap_draw_mat   包 draw_mat（当前直接透传）
  这样 Agent 框架注册工具时，数据在 Python 进程内流动，
  不需要把大 JSON 反复传进传出。
"""
from draw_mat import get_cached_process_data, remember_process_data, wrap_data_get
from draw_mat import draw_mat as _draw_mat


def wrap_draw_mat(fn=None):
    """返回可注册的 draw_mat（默认用 draw_mat.draw_mat 本体）。"""
    return fn or _draw_mat
