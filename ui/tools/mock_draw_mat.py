# -*- coding: utf-8 -*-
"""Mock draw_mat —— 模拟 MATLAB 出图。

真实版对应 CMV1/draw_mat.py（经 matlab_backend 调 MATLAB Engine），
写入 context["figure_path"]，将来直接替换。
图用 matplotlib 生成（白底，贴近 MATLAB 输出观感）；无 matplotlib 时退回 PIL。
"""

from __future__ import annotations

import random
import threading
import time
from pathlib import Path
from typing import Any

from .base import LogFn, ToolBase, ToolResult, ToolStopped
from .mock_data_get import STREAM_DATA

FIGURE_NAME = "figure.png"


def generate_figure(run_dir: str | Path, seed: int = 0) -> str:
    """生成 Mock 分析图（seed 变化会让数据轻微抖动，供[重新绘图]演示）。"""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / FIGURE_NAME

    rng = random.Random(seed)
    comps = [c.split(" ")[0] for c in STREAM_DATA["components"]]
    frac = [r[1] for r in STREAM_DATA["mole_fraction"]["rows"]]
    frac = [max(0.0, f + rng.uniform(-0.008, 0.008)) for f in frac]
    total = sum(frac) or 1.0
    frac = [f / total for f in frac]
    mass = [r[1] for r in STREAM_DATA["mass_flow"]["rows"]]

    try:
        return _with_matplotlib(out, comps, frac, mass)
    except ImportError:
        return _with_pil(out, comps, frac, mass)


def _with_matplotlib(out: Path, comps, frac, mass) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), dpi=110)
    colors = ["#4C78A8", "#F58518", "#54A24B"]

    ax = axes[0]
    ax.bar(comps, frac, color=colors, width=0.55)
    ax.set_title("S10 摩尔分率 (Mole Fraction)")
    ax.set_ylabel("摩尔分率 / -")
    for i, f in enumerate(frac):
        ax.text(i, f + 0.02, f"{f:.4f}", ha="center", fontsize=9)
    ax.set_ylim(0, 1.15)

    ax = axes[1]
    ax.bar(comps, mass, color=colors, width=0.55)
    ax.set_title("S10 质量流量 (Mass Flow)")
    ax.set_ylabel("质量流量 / (kg/h)")
    for i, m in enumerate(mass):
        ax.text(i, m + max(mass) * 0.02, f"{m:,.1f}", ha="center", fontsize=9)
    ax.set_ylim(0, max(mass) * 1.18)
    ax.ticklabel_format(style="plain", axis="y", scilimits=(0, 0))

    fig.suptitle("S10 物流组成分析（Mock MATLAB Output）", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out)
    plt.close(fig)
    return str(out)


def _with_pil(out: Path, comps, frac, mass) -> str:
    from PIL import Image, ImageDraw

    w, h = 1050, 420
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    dr.text((20, 14), "S10 物流组成分析（Mock, PIL fallback）", fill="black")
    colors = ["#4C78A8", "#F58518", "#54A24B"]
    # 左：摩尔分率
    for i, (c, f) in enumerate(zip(comps, frac)):
        x = 60 + i * 160
        bh = int(f / 1.0 * 280)
        dr.rectangle([x, 370 - bh, x + 90, 370], fill=colors[i % 3])
        dr.text((x, 378), c, fill="black")
        dr.text((x, 370 - bh - 16), f"{f:.4f}", fill="black")
    # 右：质量流量
    mx = max(mass) or 1.0
    for i, (c, m) in enumerate(zip(comps, mass)):
        x = 580 + i * 160
        bh = int(m / mx * 280)
        dr.rectangle([x, 370 - bh, x + 90, 370], fill=colors[i % 3])
        dr.text((x, 378), c, fill="black")
        dr.text((x, 370 - bh - 16), f"{m:,.1f}", fill="black")
    img.save(out)
    return str(out)


class MockDrawMatTool(ToolBase):
    name = "draw_mat"
    display_name = "draw_mat"
    cn_name = "MATLAB 绘图"
    description = "调 MATLAB 绘制股流组成图，输出 figure.png"

    def execute(
        self,
        task: str,
        context: dict[str, Any],
        log: LogFn,
        stop: threading.Event,
    ) -> ToolResult:
        log("Tool: draw_mat", "Starting MATLAB...")
        time.sleep(0.7)
        if stop.is_set():
            raise ToolStopped
        log("Tool: draw_mat", "✓ MATLAB connected", ok=True)
        time.sleep(0.3)
        log("Tool: draw_mat", "Drawing...")
        time.sleep(0.8)
        if stop.is_set():
            raise ToolStopped

        fig_path = generate_figure(context.get("run_dir", "."), seed=int(time.time()) % 1000)
        log("Tool: draw_mat", "✓ Plot completed", ok=True)
        time.sleep(0.2)

        return ToolResult(
            success=True,
            message="✓ figure.png 已生成",
            data={"figure_path": fig_path},
        )
