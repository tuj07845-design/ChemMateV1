# -*- coding: utf-8 -*-
"""
ChemMate V1 — 表格拆分（tables）

按四种图种从 process_data 拆出 MATLAB 要画的行数据：
    stream_tp          流股温度-压力        → stream, T, P
    stream_composition 物流组成            → component, fraction
    component_track    组分沿流股分布      → stream, value
    balance_check      设备进出衡算        → side, name, value

拆数是 Python 的数据工程职责（Agent 不负责拆数）；
拆完由 draw_mat 写 job 交给 MATLAB 画图。

约定：出错抛 DrawError(code, message)，
code 用于 Agent 端归类（missing_process_data / spec_invalid / data_not_found / unknown_plot_type）。
"""

from __future__ import annotations

from typing import Any


PLOT_TYPES = (
    "stream_tp",
    "stream_composition",
    "component_track",
    "balance_check",
)


class DrawError(Exception):
    """拆表失败。code 供上层稳定匹配，message 给人/模型读。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _number(value: Any) -> float | None:
    """宽松转 float：None / bool / 非法字符串返回 None，不做抛错。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vu(data: Any) -> tuple[float | None, str]:
    """从 {value, unit} 结构取值；裸数值（如直接 250）也兼容。"""
    if isinstance(data, dict):
        return _number(data.get("value")), str(data.get("unit") or "")
    return _number(data), ""


def _streams(process_data: dict) -> dict:
    """取 streams 字典；无效/空则抛 missing_process_data。"""
    streams = process_data.get("streams")
    if not isinstance(streams, dict) or not streams:
        raise DrawError("missing_process_data", "process_data.streams 无效或为空")
    return streams


def _lookup_component(mapping: Any, component: str) -> tuple[str | None, Any]:
    """在组分映射里按名字找组分（大小写不敏感），返回 (实际键名, 数据)。"""
    if not isinstance(mapping, dict):
        return None, None
    target = str(component).lower()
    for name in mapping:
        if str(name).lower() == target:
            return str(name), mapping[name]
    return None, None


def _stream_total_mole_flow(stream: dict) -> float | None:
    """流股的总摩尔流量（各组分 mole_flow 求和）；无数据返回 None。"""
    mole_flow = stream.get("mole_flow")
    if not isinstance(mole_flow, dict) or not mole_flow:
        return None
    total = 0.0
    seen = False
    for item in mole_flow.values():
        v, _ = _vu(item)
        if v is None:
            continue
        seen = True
        total += v
    return total if seen else None


def split_stream_tp(process_data: dict, streams: list[str] | None) -> tuple[list[dict], list[str], dict]:
    """拆 stream_tp 表：每条流股一行 stream/T/P。

    streams 参数可筛选；缺 T/P 或流股不存在的行跳过并记 warnings；
    一个可画的行都没有则抛 data_not_found。
    """
    all_streams = _streams(process_data)
    names = list(streams) if streams else list(all_streams.keys())
    rows: list[dict] = []
    warnings: list[str] = []
    t_unit = p_unit = ""

    for name in names:
        key = str(name)
        if key not in all_streams:
            warnings.append(f"流股 {key} 不在 streams 中，已跳过")
            continue
        s = all_streams[key] if isinstance(all_streams[key], dict) else {}
        t, tu = _vu(s.get("temperature"))
        p, pu = _vu(s.get("pressure"))
        if t is None or p is None:
            warnings.append(f"流股 {key} 缺温度或压力，已跳过")
            continue
        if tu:
            t_unit = tu
        if pu:
            p_unit = pu
        rows.append({"stream": key, "T": t, "P": p})

    if not rows:
        raise DrawError("data_not_found", "没有可画的流股 T/P 数据")

    # 轴标签带上单位（如 Temperature / C），传给 MATLAB 做 ylabel
    return rows, warnings, {
        "ylabel_left": f"Temperature / {t_unit}" if t_unit else "Temperature",
        "ylabel_right": f"Pressure / {p_unit}" if p_unit else "Pressure",
    }


def split_stream_composition(process_data: dict, stream: str | None) -> tuple[list[dict], list[str], dict]:
    """拆 stream_composition 表：指定流股的组分-分率表。

    stream 必填；该流股必须有 mole_fraction。
    """
    if not stream:
        raise DrawError("spec_invalid", "stream_composition 需要参数 stream")
    all_streams = _streams(process_data)
    if stream not in all_streams:
        raise DrawError("data_not_found", f"找不到物流 {stream}")

    s = all_streams[stream] if isinstance(all_streams[stream], dict) else {}
    mf = s.get("mole_fraction")
    if not isinstance(mf, dict) or not mf:
        raise DrawError("data_not_found", f"{stream} 没有 mole_fraction")

    rows: list[dict] = []
    unit = ""
    for name, item in mf.items():
        v, u = _vu(item)
        if v is None:
            continue
        if u:
            unit = u
        rows.append({"component": str(name), "fraction": v})

    if not rows:
        raise DrawError("data_not_found", f"{stream} 的 mole_fraction 没有有效数值")

    ylabel = f"Mole fraction / {unit}" if unit else "Mole fraction"
    return rows, [], {"ylabel": ylabel}


def split_component_track(
    process_data: dict,
    component: str | None,
    value_field: str = "mole_fraction",
) -> tuple[list[dict], list[str], dict]:
    """拆 component_track 表：某组分在各流股的值。

    component 必填（中文名或 Aspen ID 均可，大小写不敏感）；
    value_field 选 mole_fraction / mole_flow / mass_flow 之一。
    返回里带 matched_component（实际命中的键名）供图注使用。
    """
    if not component:
        raise DrawError("spec_invalid", "component_track 需要参数 component")

    field = (value_field or "mole_fraction").strip()
    if field not in ("mole_fraction", "mole_flow", "mass_flow"):
        raise DrawError("spec_invalid", "value_field 必须是 mole_fraction / mole_flow / mass_flow")

    all_streams = _streams(process_data)
    rows: list[dict] = []
    warnings: list[str] = []
    unit = ""
    matched_name = None

    for stream_name, stream in all_streams.items():
        if not isinstance(stream, dict):
            continue
        real, item = _lookup_component(stream.get(field), component)
        if real is None:
            continue
        matched_name = real
        v, u = _vu(item)
        if v is None:
            warnings.append(f"{stream_name} 的 {real} 无有效 {field}")
            continue
        if u:
            unit = u
        rows.append({"stream": str(stream_name), "value": v})

    if not rows:
        raise DrawError(
            "data_not_found",
            f"在 {field} 中找不到组分 {component}（用 Aspen ID，如 CYCLO-01）",
        )

    ylabel = f"{matched_name} {field}"
    if unit:
        ylabel = f"{ylabel} / {unit}"
    return rows, warnings, {"ylabel": ylabel, "matched_component": matched_name}


def split_balance_check(process_data: dict, block: str | None) -> tuple[list[dict], list[str], dict]:
    """拆 balance_check 表：设备的进/出流股总摩尔流量。

    block 必填；从 connections 找该设备的 inputs/outputs，
    每条流股用 mole_flow 总和作为 value（side = in | out）。
    """
    if not block:
        raise DrawError("spec_invalid", "balance_check 需要参数 block")

    connections = process_data.get("connections")
    if not isinstance(connections, list):
        raise DrawError("missing_process_data", "process_data.connections 无效")

    # 在 connections 里找目标设备
    conn = None
    for item in connections:
        if isinstance(item, dict) and str(item.get("block")) == str(block):
            conn = item
            break
    if conn is None:
        raise DrawError("data_not_found", f"找不到设备 {block} 的 connections")

    inputs = conn.get("inputs") or []
    outputs = conn.get("outputs") or []
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise DrawError("spec_invalid", f"{block} 的 inputs/outputs 不是列表")
    if not inputs or not outputs:
        raise DrawError("data_not_found", f"{block} 缺少输入或输出流股")

    all_streams = _streams(process_data)
    rows: list[dict] = []
    warnings: list[str] = []
    unit = ""

    def add_side(side: str, names: list) -> None:
        """把一个方向的流股逐条加进表；缺失/无流量的跳过并记警告。"""
        nonlocal unit
        for name in names:
            key = str(name)
            if key not in all_streams:
                warnings.append(f"{block} 的 {side} 流股 {key} 不在 streams 中，已跳过")
                continue
            s = all_streams[key] if isinstance(all_streams[key], dict) else {}
            total = _stream_total_mole_flow(s)
            if total is None:
                warnings.append(f"{key} 没有可用的 mole_flow 总和，已跳过")
                continue
            mf = s.get("mole_flow")
            if isinstance(mf, dict) and mf:
                _, u = _vu(next(iter(mf.values())))
                if u:
                    unit = u
            rows.append({"side": side, "name": key, "value": total})

    add_side("in", inputs)
    add_side("out", outputs)

    # 进/出必须都有数据，否则衡算图没有对比意义
    has_in = any(r["side"] == "in" for r in rows)
    has_out = any(r["side"] == "out" for r in rows)
    if not has_in or not has_out:
        raise DrawError("data_not_found", f"{block} 无法同时得到进料和出料流量")

    ylabel = f"Mole flow / {unit}" if unit else "Mole flow"
    return rows, warnings, {"ylabel": ylabel}


def split_for_plot(
    plot_type: str,
    process_data: dict,
    *,
    streams: list[str] | None = None,
    stream: str | None = None,
    component: str | None = None,
    block: str | None = None,
    value_field: str = "mole_fraction",
) -> tuple[list[dict], list[str], dict]:
    """四种图的拆分入口：校验 plot_type 与数据有效性后按图种分发。"""
    pt = (plot_type or "").strip().lower()
    if pt not in PLOT_TYPES:
        raise DrawError(
            "unknown_plot_type",
            f"不支持 plot_type={plot_type}。只能是: {', '.join(PLOT_TYPES)}",
        )
    if not isinstance(process_data, dict):
        raise DrawError("missing_process_data", "process_data 不是 dict")
    if process_data.get("success") is False:
        raise DrawError(
            "missing_process_data",
            "data_get 失败：" + str(process_data.get("error", "未知错误")),
        )

    if pt == "stream_tp":
        return split_stream_tp(process_data, streams)
    if pt == "stream_composition":
        return split_stream_composition(process_data, stream)
    if pt == "component_track":
        return split_component_track(process_data, component, value_field)
    return split_balance_check(process_data, block)
