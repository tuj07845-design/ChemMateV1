
from __future__ import annotations




# 合法的 section 类型
SECTION_TYPES = ("heading", "paragraph", "bullets", "table", "image")





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




