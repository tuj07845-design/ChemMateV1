# -*- coding: utf-8 -*-
"""
ChemMate V1 — draw_mat

Agent 只传 plot_type 和短参数。
完整 process_data：
  1. 优先用参数（一般不要让 Agent 传）
  2. 否则用最近一次 remember_process_data / wrap_data_get 缓存
然后在本模块内按四种图拆表，再交给 MATLAB。
"""

from __future__ import annotations

import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from jobs import create_job_dir, read_result, write_job
from matlab_backend import MatlabFailed, run_draw_dispatch
from tables import DrawError, PLOT_TYPES, split_for_plot

TOOL_NAME = "draw_mat"

TOOL_DESCRIPTION = (
    "根据最近一次 data_get_process 的结果画一张图。"
    "不要传入 process_data。"
    "plot_type 只能是 stream_tp / stream_composition / component_track / balance_check。"
    "禁止 sankey 或其它类型。"
    "stream_composition 必须带 stream；component_track 必须带 component（Aspen ID，如 CYCLO-01）；"
    "balance_check 必须带 block。"
)

TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "plot_type": {
            "type": "string",
            "enum": list(PLOT_TYPES),
            "description": "stream_tp | stream_composition | component_track | balance_check",
        },
        "streams": {"type": "array", "items": {"type": "string"}},
        "stream": {"type": "string"},
        "component": {"type": "string"},
        "block": {"type": "string"},
        "value_field": {
            "type": "string",
            "enum": ["mole_fraction", "mole_flow", "mass_flow"],
        },
        "title": {"type": "string"},
        "export": {"type": "string", "enum": ["png", "svg"]},
    },
    "required": ["plot_type"],
}

_LAST_PROCESS_DATA: dict[str, Any] | None = None


def remember_process_data(data: Any) -> Any:
    """data_get 成功后调用，把结果缓存在 Python。"""
    global _LAST_PROCESS_DATA
    if isinstance(data, dict) and data.get("success"):
        _LAST_PROCESS_DATA = data
    return data


def get_cached_process_data() -> dict[str, Any] | None:
    """取回最近一次缓存的 data_get 结果（无缓存返回 None）。"""
    return _LAST_PROCESS_DATA


def wrap_data_get(fn: Callable) -> Callable:
    """包一层 data_get_process：返回值自动缓存。"""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        return remember_process_data(fn(*args, **kwargs))

    return wrapped


def _fail(plot_type: str, code: str, message: str, warnings: list[str] | None = None) -> dict:
    """统一构造失败返回体：code 与 message 供 Agent 定位原因。"""
    return {
        "success": False,
        "plot_type": plot_type,
        "error": code,
        "message": message,
        "image_path": "",
        "caption": "",
        "meta": {},
        "warnings": warnings or [],
        "job_dir": "",
    }


def _caption(plot_type: str, title: str, extra: dict) -> str:
    """生成图注：有显式 title 用它，否则按图种给默认中文说明。"""
    if title:
        return title
    if plot_type == "stream_tp":
        return "流股温度与压力"
    if plot_type == "stream_composition":
        return "物流组成"
    if plot_type == "component_track":
        return f"{extra.get('matched_component') or '组分'} 沿流股分布"
    if plot_type == "balance_check":
        return "设备进/出衡算"
    return plot_type


def _default_draw_path() -> Path:
    """定位 MATLAB draw 目录（含 draw_dispatch.m）。

    优先级：环境变量 CHEMMATE_MATLAB_DRAW > 相对仓库根目录的 matlab/draw。
    """
    env = os.environ.get("CHEMMATE_MATLAB_DRAW")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # ds: 重组后 draw_mat.py 位于 CMV1/，matlab/draw 就在同级的
    # ds: CMV1/matlab/draw，即 parents[0]；旧版只试 parents[1]/[2] 导致找不到
    for cand in (
        here.parents[0] / "matlab" / "draw",
        here.parents[1] / "matlab" / "draw",
        here.parents[2] / "matlab" / "draw",
    ):
        if (cand / "draw_dispatch.m").is_file():
            return cand
    return here.parents[0] / "matlab" / "draw"


def _default_jobs_root() -> Path:
    """job 目录根：环境变量 CHEMMATE_JOBS_DIR，默认当前目录下 jobs/。"""
    env = os.environ.get("CHEMMATE_JOBS_DIR")
    if env:
        return Path(env)
    return Path.cwd() / "jobs"


def _resolve_process_data(process_data: dict | None) -> dict:
    """确定绘图用的流程数据。

    优先级：
      1. 显式传入的 process_data（一般不要用，让 Agent 少传大 JSON）
      2. 最近一次 data_get_process 的缓存（remember_process_data）
    两者都没有则抛 DrawError。
    """
    if isinstance(process_data, dict) and process_data:
        remember_process_data(process_data)
        return process_data
    cached = get_cached_process_data()
    if cached is None:
        raise DrawError(
            "missing_process_data",
            "没有流程数据。请先调用 data_get_process（不要把 JSON 传给 draw_mat）。",
        )
    return cached


def draw_mat(
    plot_type: str,
    process_data: dict | None = None,
    streams: list[str] | None = None,
    stream: str | None = None,
    component: str | None = None,
    block: str | None = None,
    value_field: str = "mole_fraction",
    title: str = "",
    export: str = "png",
    matlab_draw_path: str | Path | None = None,
    jobs_root: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """ChemMate V1 画图统一入口。

    流程：确定数据 -> 按图种拆表 -> 写 job（request.json + data.csv）
          -> 调 MATLAB draw_dispatch 出图 -> 读 result.json 回传。

    参数：
        plot_type  图种：stream_tp / stream_composition / component_track / balance_check
        process_data  流程数据（一般让 Agent 不传，用缓存）
        streams / stream / component / block / value_field  拆表的筛选参数
        title  图标题；export  png 或 svg
        dry_run  只拆表写 job，不调 MATLAB（调试用）

    返回：统一 dict（success / error / message / image_path / caption / meta / warnings / job_dir）
    """
    # ---- 参数规整与 export 白名单校验 ----
    pt = (plot_type or "").strip().lower()
    export_fmt = (export or "png").strip().lower()
    if export_fmt not in ("png", "svg"):
        return _fail(pt, "spec_invalid", "export 必须是 png 或 svg")

    # ---- 取数据并按图种拆成 MATLAB 要的表（stream, T, P ...） ----
    try:
        data = _resolve_process_data(process_data)
        rows, warnings, labels = split_for_plot(
            pt,
            data,
            streams=streams,
            stream=stream,
            component=component,
            block=block,
            value_field=value_field or "mole_fraction",
        )
    except DrawError as exc:
        return _fail(pt, exc.code, exc.message)

    # ---- 写 job：request.json（请求）+ data.csv（拆好的表） ----
    job_dir = create_job_dir(jobs_root or _default_jobs_root())
    auto_title = title or _caption(pt, title, labels)
    write_job(
        job_dir,
        pt,
        rows,
        title=auto_title,
        export=export_fmt,
        ylabel=str(labels.get("ylabel") or ""),
        ylabel_left=str(labels.get("ylabel_left") or ""),
        ylabel_right=str(labels.get("ylabel_right") or ""),
    )

    # ---- 调试模式：不调 MATLAB，只看拆表结果 ----
    if dry_run:
        return {
            "success": True,
            "plot_type": pt,
            "error": "",
            "message": "dry_run: 已按图种拆表并写 job，未调 MATLAB",
            "image_path": "",
            "caption": auto_title,
            "meta": {"n_rows": len(rows), **{k: v for k, v in labels.items() if k == "matched_component"}},
            "warnings": warnings,
            "job_dir": str(job_dir),
        }

    # ---- 调 MATLAB：draw_dispatch 出图，失败按 matlab_failed 归类 ----
    draw_path = Path(matlab_draw_path) if matlab_draw_path else _default_draw_path()
    try:
        run_draw_dispatch(job_dir, draw_path)
    except MatlabFailed as exc:
        return _fail(pt, "matlab_failed", exc.message, warnings)

    # ---- 读 MATLAB 回写的 result.json，成功则带图路径返回 ----
    matlab_res = read_result(job_dir)
    if not matlab_res.get("ok"):
        return _fail(
            pt,
            str(matlab_res.get("error") or "matlab_failed"),
            str(matlab_res.get("message") or "MATLAB 绘图失败"),
            warnings,
        )

    image_path = str(matlab_res.get("image_path") or (job_dir / f"figure.{export_fmt}"))
    return {
        "success": True,
        "plot_type": pt,
        "error": "",
        "message": "",
        "image_path": image_path,
        "caption": auto_title,
        "meta": matlab_res.get("meta") or {},
        "warnings": warnings,
        "job_dir": str(job_dir),
    }


def tool_spec() -> dict:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "parameters": TOOL_PARAMETERS,
    }
