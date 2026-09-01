# -*- coding: utf-8 -*-
"""
ChemMate V1 — job 目录管理（Python ↔ MATLAB 的中间层）

约定：每次绘图生成一个 job 目录（jobs/draw_xxxxxxxx），里面放：
    request.json   绘图请求（plot_type / title / export / 轴标签）
    data.csv       拆好的绘图数据表
    result.json    MATLAB 回写的结果（ok / error / message / image_path / meta）

本模块只负责目录创建、写入、读取，不含绘图逻辑。
"""
from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Any


def create_job_dir(jobs_root: str | Path) -> Path:
    """在 jobs_root 下创建一个唯一 job 目录（draw_ 前缀 + 8 位随机 hex）。"""
    root = Path(jobs_root)
    root.mkdir(parents=True, exist_ok=True)
    job = root / f"draw_{uuid.uuid4().hex[:8]}"
    job.mkdir(parents=True, exist_ok=True)
    return job


def write_job(
    job_dir: Path,
    plot_type: str,
    rows: list[dict],
    *,
    title: str = "",
    export: str = "png",
    ylabel: str = "",
    ylabel_left: str = "",
    ylabel_right: str = "",
) -> None:
    """把拆好的表写成 data.csv，请求写成 request.json。

    data.csv 的列名取 rows 第一行的键（如 stream, T, P），
    request.json 里带 plot_type 与可选轴标签，供 MATLAB 端读取。
    """
    if not rows:
        raise ValueError("rows is empty")
    keys = list(rows[0].keys())
    # 写 CSV：UTF-8，表头 = 键名
    with (job_dir / "data.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

    # 写请求：MATLAB 端 jsondecode 后按字段取值
    req = {
        "plot_type": plot_type,
        "title": title or "",
        "export": export or "png",
        "ylabel": ylabel or "",
        "ylabel_left": ylabel_left or "",
        "ylabel_right": ylabel_right or "",
    }
    (job_dir / "request.json").write_text(
        json.dumps(req, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_result(job_dir: Path) -> dict[str, Any]:
    """读 MATLAB 回写的 result.json，保证返回体字段齐全。

    文件缺失 / 解析失败 / 非对象时返回 ok=False 的兜底结构，
    不会向上抛异常（画图失败应走工具返回，而不是让 Agent 崩溃）。
    """
    path = job_dir / "result.json"
    if not path.is_file():
        return {
            "ok": False,
            "error": "matlab_failed",
            "message": "MATLAB 未写出 result.json",
            "image_path": "",
            "meta": {},
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": "matlab_failed",
            "message": f"result.json 无法解析: {exc}",
            "image_path": "",
            "meta": {},
        }
    if not isinstance(data, dict):
        return {
            "ok": False,
            "error": "matlab_failed",
            "message": "result.json 不是对象",
            "image_path": "",
            "meta": {},
        }
    # 补齐缺失字段，让调用方不用每次防御式取值
    data.setdefault("ok", False)
    data.setdefault("error", "")
    data.setdefault("message", "")
    data.setdefault("image_path", "")
    data.setdefault("meta", {})
    return data
