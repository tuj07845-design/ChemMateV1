from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from .render_docx import _render_docx
from .render_pptx import _render_pptx



SECTION_TYPES = ("heading", "paragraph", "bullets", "table", "image")

class ReportError(Exception):
    """报告生成失败。code 供上层稳定匹配。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ============================================================
# 缺依赖检测
# ============================================================

def _check_lib(report_type: str) -> None:
    """按格式检测依赖库，缺失给清晰指引。"""
    if report_type == "docx":
        try:
            import docx  # noqa: F401
        except ImportError:
            raise ReportError(
                "missing_dependency",
                "生成 Word 报告需要 python-docx，请执行：pip install python-docx",
            )
    elif report_type == "pptx":
        try:
            import pptx  # noqa: F401
        except ImportError:
            raise ReportError(
                "missing_dependency",
                "生成 PPT 报告需要 python-pptx，请执行：pip install python-pptx",
            )


# ============================================================
# section 校验
# ============================================================

def _validate_sections(sections: list) -> list:
    """校验并规整 sections；非法块抛 ReportError。"""
    if not isinstance(sections, list):
        raise ReportError("spec_invalid", "sections 必须是列表")

    cleaned = []
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict):
            raise ReportError("spec_invalid", f"第 {i + 1} 块不是 dict")
        stype = sec.get("type")
        if stype not in SECTION_TYPES:
            raise ReportError(
                "spec_invalid",
                f"第 {i + 1} 块 type={stype!r} 非法，可选 {SECTION_TYPES}",
            )
        cleaned.append(sec)
    return cleaned

def _reports_root() -> Path:
    """报告根目录：环境变量 > 项目内 CMV1/reports。

    ★ 不能用 Path.cwd()：UI 从 CMV1/ui 启动时 cwd 就是 CMV1/ui，
      报告会落到 CMV1/ui/reports，而前端只放行 CMV1/jobs、CMV1/reports、
      CMV1/ui/runs —— 结果就是「报告生成了但前端看不到、也打不开」（403）。
      改为相对本文件定位，保证与启动方式无关。
    """
    env = os.environ.get("CHEMMATE_REPORTS_DIR")
    if env and str(env).strip():
        return Path(env)
    # 本文件在 CMV1/tools/report_create/ 下：parents[2] == CMV1
    return Path(__file__).resolve().parents[2] / "reports"


def _resolve_output_path(report_type: str, title: str, output_path: str | Path | None) -> Path:
    """统一把报告收拢到 reports 目录（CHEMMATE_REPORTS_DIR，默认 CMV1/reports）。

    未传 output_path → 标题 + 时间戳命名；
    传入路径在 reports 根内 → 原样使用；
    越界路径（别的目录 / 相对路径）→ 只取文件名落回 reports 根，
    保证所有报告都收在统一目录里（UI 产物登记依赖该约定）。
    """
    root = _reports_root()
    root.mkdir(parents=True, exist_ok=True)
    if output_path:
        candidate = Path(output_path)
        try:
            if candidate.resolve().is_relative_to(root.resolve()):
                return candidate
        except OSError:
            pass
        return root / candidate.name
    # 文件名：标题前若干字 + 时间戳，去非法字符
    safe = "".join(c for c in title if c not in r'\/:*?"<>|')[:20].strip() or "report"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / f"{safe}_{stamp}.{report_type}"


# ============================================================
# 主入口
# ============================================================

def report_create(
    report_type: str,
    title: str,
    sections: list,
    output_path: str | Path | None = None,
    author: str = "ChemMate V1",
) -> dict[str, Any]:
    """生成 Word / PPT 报告。

    返回统一 dict：
        success / error / message / file_path / report_type / section_count
    """
    rt = (report_type or "").strip().lower()
    if rt not in ("docx", "pptx"):
        return _fail("spec_invalid", "report_type 必须是 docx 或 pptx")

    if not title or not str(title).strip():
        return _fail("spec_invalid", "title 不能为空")

    try:
        sections = _validate_sections(sections)
    except ReportError as exc:
        return _fail(exc.code, exc.message)

    try:
        _check_lib(rt)
    except ReportError as exc:
        return _fail(exc.code, exc.message)

    out = _resolve_output_path(rt, str(title), output_path)
    # 保证扩展名
    if out.suffix.lower() != f".{rt}":
        out = out.with_suffix(f".{rt}")

    try:
        if rt == "docx":
            _render_docx(str(title), sections, out, author)
        else:
            _render_pptx(str(title), sections, out, author)
    except ReportError as exc:
        return _fail(exc.code, exc.message)
    except Exception as exc:
        return _fail("render_failed", f"{type(exc).__name__}: {exc}")

    return {
        "success": True,
        "error": "",
        "message": f"已生成 {rt} 报告，共 {len(sections)} 个内容块",
        "file_path": str(out),
        "report_type": rt,
        "section_count": len(sections),
    }


def _fail(code: str, message: str) -> dict:
    return {
        "success": False,
        "error": code,
        "message": message,
        "file_path": "",
        "report_type": "",
        "section_count": 0,
    }
