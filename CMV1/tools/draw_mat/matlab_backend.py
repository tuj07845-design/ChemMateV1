# -*- coding: utf-8 -*-
"""
ChemMate V1 — MATLAB 后端调用

draw_mat 不直接拼 matlab -batch 命令，
而是统一走本模块的 run_draw_dispatch：

    调用模式（环境变量 CHEMMATE_MATLAB_MODE 控制）：
        engine   只用 MATLAB Engine（matlab.engine）
        batch    只用 matlab -batch 子进程（无需 Engine 包）
        auto     默认：先试 Engine，失败/不可用再回退 batch

说明：
    - MATLAB Engine 官方只支持 Python 3.9~3.12，
      Python 3.13 下 import 会报 UserWarning，这里会静默抑制；
      且 Engine 依赖 MATLAB 注册到系统（find_matlab 能找到），
      绿色安装（未注册）时 start_matlab 会失败，应改用 batch。
    - batch 模式只需设置 CHEMMATE_MATLAB_BIN 指向 matlab.exe，
      例如：E:\\AM1\\bin\\matlab.exe

失败统一抛 MatlabFailed，由 draw_mat 归类为 matlab_failed。
"""
from __future__ import annotations

import os
import subprocess
import warnings
from pathlib import Path


class MatlabFailed(Exception):
    """MATLAB 调用失败（找不到引擎 / 超时 / 非零退出 / 缺 draw_dispatch.m）。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _posix(path: Path) -> str:
    """路径转 POSIX 风格（MATLAB 命令里避免反斜杠转义问题）。"""
    return path.resolve().as_posix()


def run_draw_dispatch(job_dir: Path, matlab_draw_path: Path, timeout: int = 180) -> None:
    """入口：先校验 draw_dispatch.m 存在，再按配置的模式调用 MATLAB。

    模式由环境变量 CHEMMATE_MATLAB_MODE 决定（engine / batch / auto）。
    """
    draw_path = matlab_draw_path.resolve()
    if not (draw_path / "draw_dispatch.m").is_file():
        raise MatlabFailed(f"找不到 draw_dispatch.m: {draw_path}")

    # ds: 调用模式由环境变量 CHEMMATE_MATLAB_MODE 控制（engine/batch/auto）
    mode = os.environ.get("CHEMMATE_MATLAB_MODE", "auto").strip().lower()

    if mode == "engine":
        _try_engine(job_dir, draw_path)  # 失败会抛 MatlabFailed
        return

    if mode == "batch":
        _run_batch(job_dir, draw_path, timeout)
        return

    # ds: auto 模式：Engine 尝试失败（如 MATLAB 未注册）自动回退 batch
    try:
        if _try_engine(job_dir, draw_path):
            return
    except MatlabFailed as engine_exc:
        # Engine 尝试失败（如 MATLAB 未注册）——回退 batch
        # 若 batch 也失败，错误信息里带上 Engine 的失败原因辅助排查
        try:
            _run_batch(job_dir, draw_path, timeout)
            return
        except MatlabFailed as batch_exc:
            raise MatlabFailed(
                f"{batch_exc.message}"
                f"（Engine 尝试也失败：{engine_exc.message}）"
            ) from batch_exc
    _run_batch(job_dir, draw_path, timeout)


def _try_engine(job_dir: Path, draw_path: Path) -> bool:
    """尝试用 MATLAB Engine 调用（需要安装 matlab.engine）。

    返回 True 表示调用成功；未安装 Engine 返回 False 走 batch 回退；
    已安装但调用出错则抛 MatlabFailed。
    """
    try:
        # MATLAB Engine 官方仅支持 Python 3.9~3.12：
        # Python 3.13 下 import 会报 UserWarning，静默抑制（不影响功能）
        with warnings.catch_warnings():
            # ds: 抑制 MATLAB Engine 在 Python 3.13 下的版本兼容 UserWarning
            # ds: （官方仅支持 3.9~3.12；3.13 下两条不同文本的警告都要拦）
            warnings.filterwarnings(
                "ignore",
                message=r"Python versions 3\.9, 3\.10, 3\.11, and 3\.12 are supported.*",
            )
            warnings.filterwarnings(
                "ignore",
                message=r"MATLAB Engine for Python supports Python version.*",
            )
            import matlab.engine  # type: ignore
    except Exception:
        return False
    try:
        eng = matlab.engine.start_matlab()
        try:
            eng.addpath(str(draw_path), nargout=0)
            eng.draw_dispatch(_posix(job_dir), nargout=0)
        finally:
            eng.quit()
        return True
    except Exception as exc:
        raise MatlabFailed(f"MATLAB Engine 调用失败: {exc}") from exc


def _discover_matlab_bin() -> str:
    """定位 matlab 可执行文件：环境变量 > PATH > 常见安装位置。

    非标准安装（如 E:\\AM1）没有注册到系统，Engine 找不到，
    但可执行文件本身能直接跑 -batch，这里做自动探测。
    """
    env = os.environ.get("CHEMMATE_MATLAB_BIN")
    if env and env.strip():
        return env.strip()

    import shutil

    found = shutil.which("matlab")
    if found:
        return found

    # ds: 常见安装位置探测（含本机 R2025b 绿色安装 E:\AM1）
    for cand in (
        r"E:\AM1\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe",
        r"D:\MATLAB\R2025b\bin\matlab.exe",
        r"D:\MATLAB\R2024b\bin\matlab.exe",
    ):
        if os.path.isfile(cand):
            return cand

    return "matlab"


def _run_batch(job_dir: Path, draw_path: Path, timeout: int) -> None:
    """回退方案：matlab -batch 子进程执行 draw_dispatch。

    MATLAB 可执行文件由 _discover_matlab_bin 自动探测，
    也可用环境变量 CHEMMATE_MATLAB_BIN 覆盖。
    """
    matlab_bin = _discover_matlab_bin()
    cmd_m = (
        f"addpath('{_posix(draw_path)}'); "
        f"draw_dispatch('{_posix(job_dir)}')"
    )
    try:
        proc = subprocess.run(
            [matlab_bin, "-batch", cmd_m],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        # ds: 找不到 MATLAB 时给出可操作的诊断指引
        raise MatlabFailed(
            f"未找到 MATLAB `{matlab_bin}`。"
            "请在系统环境变量设置 "
            "CHEMMATE_MATLAB_BIN=<matlab.exe 完整路径>（如 E:\\AM1\\bin\\matlab.exe），"
            "或设置 CHEMMATE_MATLAB_MODE=batch 强制走 batch 模式。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MatlabFailed(f"MATLAB 超时（{timeout}s）") from exc

    # 非零退出码：把 stderr/stdout 带回给调用方
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise MatlabFailed(err or f"matlab -batch 退出码 {proc.returncode}")
