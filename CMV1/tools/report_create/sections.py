



TOOL_NAME = "report_create"

TOOL_DESCRIPTION = (
    "生成 Word(.docx) 或 PPT(.pptx) 分析报告。"
    "把要写进报告的内容按 sections 传入；"
    "图片用 image 类型，path 填 draw_mat 返回的 image_path。"
    "report_type 为 docx 或 pptx。"
    "输出已按中文阅读排版（Word：宋体正文/黑体标题/1.5 倍行距；PPT：微软雅黑）。"
)

TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "report_type": {
            "type": "string",
            "enum": ["docx", "pptx"],
            "description": "报告格式：docx（Word）或 pptx（PowerPoint）",
        },
        "title": {
            "type": "string",
            "description": "报告标题",
        },
        "sections": {
            "type": "array",
            "description": "内容块列表，每块一个 dict，见模块文档",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["heading", "paragraph", "bullets", "table", "image"],
                    },
                    "level": {"type": "integer", "description": "heading 用，1~3"},
                    "text": {"type": "string", "description": "heading/paragraph 用"},
                    "items": {"type": "array", "items": {"type": "string"}, "description": "bullets 用"},
                    "headers": {"type": "array", "items": {"type": "string"}, "description": "table 用"},
                    "rows": {"type": "array", "description": "table 用，每行一个值列表"},
                    "path": {"type": "string", "description": "image 用，图片路径"},
                    "caption": {"type": "string", "description": "image 用，图注"},
                },
                "required": ["type"],
            },
        },
        "output_path": {
            "type": "string",
            "description": "输出文件路径；不传则默认放 reports/ 下",
        },
        "author": {
            "type": "string",
            "description": "作者/署名，默认 ChemMate V1",
        },
    },
    "required": ["report_type", "title", "sections"],
}

# 合法的 section 类型
SECTION_TYPES = ("heading", "paragraph", "bullets", "table", "image")




from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

# ============================================================
# 便捷：从 analyze 结果 + 图片快速组装 sections
# ============================================================

def build_sections_from_results(
    process_data: dict | None = None,
    analyze_result: dict | None = None,
    image_paths: list[str] | None = None,
    intro: str = "",
) -> list[dict]:
    """把 data_get / analyze / draw_mat 的结果快速拼成 sections。

    Agent 也可自己组织 sections，本函数只是省事用的便捷构造。
    返回的 sections 可直接传给 report_create。
    """
    sections: list[dict] = []

    if intro:
        sections.append({"type": "paragraph", "text": intro})

    # 流程概况表（来自 data_get）
    if isinstance(process_data, dict) and process_data.get("success"):
        streams = process_data.get("streams", {})
        if isinstance(streams, dict) and streams:
            sections.append({"type": "heading", "level": 1, "text": "一、流程概况"})
            blocks = process_data.get("blocks", [])
            conns = process_data.get("connections", [])
            sections.append({"type": "paragraph", "text": f"设备 {len(blocks)} 个，物流 {len(streams)} 条，连接 {len(conns)} 条。"})
            # 设备表
            if isinstance(conns, list) and conns:
                headers = ["设备", "输入", "输出"]
                rows = []
                for c in conns:
                    if not isinstance(c, dict):
                        continue
                    rows.append([
                        str(c.get("block", "")),
                        ", ".join(str(x) for x in (c.get("inputs") or [])),
                        ", ".join(str(x) for x in (c.get("outputs") or [])),
                    ])
                if rows:
                    sections.append({"type": "table", "headers": headers, "rows": rows})

    # 分析结果（来自 analyze_process）
    if isinstance(analyze_result, dict) and analyze_result.get("success"):
        sections.append({"type": "heading", "level": 1, "text": "二、数据分析"})

        summary = analyze_result.get("summary", {})
        if isinstance(summary, dict):
            items = []
            for k, v in summary.items():
                items.append(f"{k}：{v}")
            if items:
                sections.append({"type": "bullets", "items": items})

        findings = analyze_result.get("findings", [])
        if isinstance(findings, list) and findings:
            sections.append({"type": "heading", "level": 2, "text": "数据检查发现"})
            items = []
            for f in findings:
                if not isinstance(f, dict):
                    continue
                items.append(
                    f"[{f.get('level', '?')}] {f.get('type', '')}"
                    + (f"（{f.get('stream', '')}）" if f.get("stream") else "")
                    + f"：{f.get('message', '')}"
                )
            sections.append({"type": "bullets", "items": items})
        else:
            sections.append({"type": "paragraph", "text": "数据检查未发现异常。"})

        tracking = analyze_result.get("component_tracking", [])
        if isinstance(tracking, list) and tracking:
            sections.append({"type": "heading", "level": 2, "text": "组分追踪"})
            headers = ["流股", "摩尔分率", "摩尔流", "质量流"]
            rows = []
            for t in tracking:
                if not isinstance(t, dict):
                    continue
                rows.append([
                    str(t.get("stream", "")),
                    _fmt(t.get("mole_fraction")),
                    _fmt_unit(t.get("mole_flow"), t.get("mole_flow_unit")),
                    _fmt_unit(t.get("mass_flow"), t.get("mass_flow_unit")),
                ])
            sections.append({"type": "table", "headers": headers, "rows": rows})

        changes = analyze_result.get("stream_changes", [])
        if isinstance(changes, list) and changes:
            sections.append({"type": "heading", "level": 2, "text": "前后变化"})
            headers = ["设备", "从", "到", "组分变化"]
            rows = []
            for c in changes:
                if not isinstance(c, dict):
                    continue
                comps = c.get("significant_components", [])
                desc = "; ".join(
                    f"{x.get('component', '')}:{_fmt(x.get('from'))}→{_fmt(x.get('to'))}"
                    for x in comps if isinstance(x, dict)
                )
                rows.append([str(c.get("block", "")), str(c.get("from_stream", "")), str(c.get("to_stream", "")), desc])
            sections.append({"type": "table", "headers": headers, "rows": rows})

    # 图片
    if image_paths:
        sections.append({"type": "heading", "level": 1, "text": "三、图表"})
        for i, p in enumerate(image_paths, 1):
            sections.append({"type": "image", "path": str(p), "caption": f"图{i}"})

    return sections


def _fmt(v) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.6g}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_unit(v, u) -> str:
    s = _fmt(v)
    if s and u:
        return f"{s} {u}"
    return s


# ============================================================
# Agent Tool 注册信息
# ============================================================

def tool_spec() -> dict:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "parameters": TOOL_PARAMETERS,
    }

