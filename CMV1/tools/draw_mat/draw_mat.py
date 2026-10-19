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

from .jobs import create_job_dir, read_result, write_job
from memory.process_cache import remember_process_data, get_cached_process_data
from .matlab_backend import MatlabFailed, run_draw_dispatch
from .tables import DrawError, split_for_plot



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

    优先级：环境变量 CHEMMATE_MATLAB_DRAW > 本模块同级的 matlab/。
    """
    env = os.environ.get("CHEMMATE_MATLAB_DRAW")
    if env and str(env).strip():
        return Path(env)
    # 本文件在 CMV1/tools/draw_mat/ 下，.m 文件在它的 matlab/ 子目录
    return Path(__file__).resolve().parent / "matlab"


def _default_jobs_root() -> Path:
    """job 目录根：环境变量 CHEMMATE_JOBS_DIR，默认项目内 CMV1/jobs。

    ★ 不能用 Path.cwd()：UI 从 CMV1/ui 启动时 cwd 就是 CMV1/ui，
      job（含 figure.png）会落到 CMV1/ui/jobs，而前端只放行
      CMV1/jobs、CMV1/reports、CMV1/ui/runs —— 图就会显示不出来。
      改为相对本文件定位，保证与启动方式无关。
    """
    env = os.environ.get("CHEMMATE_JOBS_DIR")
    if env and str(env).strip():
        return Path(env)
    # 本文件在 CMV1/tools/draw_mat/ 下：parents[2] == CMV1
    return Path(__file__).resolve().parents[2] / "jobs"


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
            "没有流程数据。请先调用 data_get_process（不要把 JSON 传给 draw_mat）。"
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
    # 目录名带上模型文件名（如 10万吨环己烷_xxxxxxxx），方便辨认任务来源
    model_name = None
    fp = data.get("file_path") if isinstance(data, dict) else None
    if fp:
        model_name = Path(str(fp)).stem
    job_dir = create_job_dir(jobs_root or _default_jobs_root(), name=model_name)
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



