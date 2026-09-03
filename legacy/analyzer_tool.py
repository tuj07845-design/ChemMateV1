# -*- coding: utf-8 -*-

"""
ChemMate V1 - Thin Analyzer

作用：
1. 接收 data_get_process_tool_v2.py 返回的结构化数据
2. 做确定性的基础数据检查
3. 做物流前后组分变化分析
4. 做指定组分追踪
5. 输出结构化结果给 Agent

注意：
- 本模块不读取 Aspen
- 本模块不负责 MATLAB
- 本模块不负责自然语言报告
- 本模块不进行复杂化工理论推理
- 化工意义由 Agent 根据本模块结果进一步判断
"""

import json


# ============================================================
# 基础工具
# ============================================================

def _number(value):
    """
    尝试把一个值转换成 float。

    支持：
        10
        10.5
        "10.5"

    不支持：
        None
        ""
        "abc"

    返回：
        float / None
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _value(data):
    """
    从：

        {
            "value": 250,
            "unit": "C"
        }

    中读取 value。
    """

    if isinstance(data, dict):
        return data.get("value")

    return data


def _unit(data):
    """
    从：

        {
            "value": 250,
            "unit": "C"
        }

    中读取 unit。
    """

    if isinstance(data, dict):
        return str(data.get("unit", ""))

    return ""


def _numeric_value(data):
    """
    直接从 data_get 的 value/unit 结构中
    获取数值。
    """

    return _number(
        _value(data)
    )


# ============================================================
# 组分别名表
# ============================================================

COMPONENT_ALIASES = {
    # 中文名（用户/Agent 常用） → 该组分的可能键名
    "甲苯": ["TOLUE-01", "TOLUENE", "C7H8"],
    "环己烷": ["CYCLO-01", "CYCLOHEXANE", "C6H12"],
    "苯": ["BENZENE", "BENZENE-01", "C6H6"],
    "氢气": ["H2", "HYDROGEN"],
    "氢": ["H2", "HYDROGEN"],
    "甲烷": ["CH4", "METHANE"],
    "氮气": ["N2", "NITROGEN"],
    "氮": ["N2", "NITROGEN"],
    "氧气": ["O2", "OXYGEN"],
    "氧": ["O2", "OXYGEN"],
    "一氧化碳": ["CO", "CARBON-MONOXIDE"],
    "二氧化碳": ["CO2", "CARBON-DIOXIDE"],
    "水": ["H2O", "WATER"],
    "甲醇": ["METHANOL", "MEOH"],
    "乙醇": ["ETHANOL", "ETOH"],
}


def _find_key(query, keys):
    """
    在 keys 中寻找与 query 匹配的键名。

    匹配优先级：
        1. 精确匹配（大小写不敏感）
        2. 别名表匹配（中文名 → Aspen ID / 英文名）
        3. 子串匹配（键包含 query，或 query 包含键）

    返回实际键名；找不到返回 None。
    """

    q = str(query).strip().lower()

    if not q:
        return None

    # 1. 精确
    for key in keys:

        if str(key).lower() == q:
            return key

    # 2. 别名
    for alias in COMPONENT_ALIASES.get(
        q,
        []
    ):

        for key in keys:

            if str(key).lower() == (
                alias.lower()
            ):
                return key

    # 3. 子串
    for key in keys:

        key_lower = str(key).lower()

        if (
            q in key_lower
            or key_lower in q
        ):
            return key

    return None


# ============================================================
# Stream 基础信息
# ============================================================

def _stream_summary(stream_name, stream):
    """
    提取一个物流的关键参数。

    不复制整个 Stream，
    避免给 Agent 制造不必要的数据量。
    """

    if not isinstance(stream, dict):
        stream = {}

    temperature = stream.get(
        "temperature"
    )

    pressure = stream.get(
        "pressure"
    )

    vapor_fraction = stream.get(
        "vapor_fraction"
    )

    return {

        "stream": stream_name,

        "temperature": {
            "value": _value(
                temperature
            ),
            "unit": _unit(
                temperature
            ),
        },

        "pressure": {
            "value": _value(
                pressure
            ),
            "unit": _unit(
                pressure
            ),
        },

        "vapor_fraction": {
            "value": _value(
                vapor_fraction
            ),
            "unit": _unit(
                vapor_fraction
            ),
        },
    }


# ============================================================
# ① 基础数据检查
# ============================================================

def check_stream(
    stream_name,
    stream
):
    """
    检查一个 Stream 的明显数据问题。

    只检查确定性问题：

    - 温度缺失
    - 压力缺失
    - 压力 <= 0
    - 气相分率 < 0
    - 气相分率 > 1
    - 质量流量 < 0
    - 摩尔流量 < 0
    - 摩尔分率 < 0
    - 摩尔分率 > 1
    - 摩尔分率总和明显偏离 1
    """

    findings = []

    if not isinstance(stream, dict):

        findings.append({
            "level": "error",
            "type": "invalid_stream",
            "stream": stream_name,
            "message": "物流数据不是有效的 dict",
        })

        return findings

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    temperature = _numeric_value(
        stream.get("temperature")
    )

    if temperature is None:

        findings.append({
            "level": "warning",
            "type": "missing_temperature",
            "stream": stream_name,
            "message": "缺少有效温度数据",
        })

    # --------------------------------------------------------
    # Pressure
    # --------------------------------------------------------

    pressure = _numeric_value(
        stream.get("pressure")
    )

    if pressure is None:

        findings.append({
            "level": "warning",
            "type": "missing_pressure",
            "stream": stream_name,
            "message": "缺少有效压力数据",
        })

    elif pressure <= 0:

        findings.append({
            "level": "error",
            "type": "invalid_pressure",
            "stream": stream_name,
            "value": pressure,
            "message": (
                f"压力为 {pressure}，"
                "小于或等于 0"
            ),
        })

    # --------------------------------------------------------
    # Vapor fraction
    # --------------------------------------------------------

    vapor_fraction = _numeric_value(
        stream.get("vapor_fraction")
    )

    if vapor_fraction is not None:

        if (
            vapor_fraction < 0
            or vapor_fraction > 1
        ):

            findings.append({
                "level": "error",
                "type": "invalid_vapor_fraction",
                "stream": stream_name,
                "value": vapor_fraction,
                "message": (
                    f"气相分率为 {vapor_fraction}，"
                    "不在 0~1 范围内"
                ),
            })

    # --------------------------------------------------------
    # Mass flow
    # --------------------------------------------------------

    mass_flow = stream.get(
        "mass_flow",
        {}
    )

    if isinstance(mass_flow, dict):

        for component, data in mass_flow.items():

            value = _numeric_value(data)

            if (
                value is not None
                and value < 0
            ):

                findings.append({
                    "level": "error",
                    "type": "negative_mass_flow",
                    "stream": stream_name,
                    "component": component,
                    "value": value,
                    "message": (
                        f"{component} "
                        f"质量流量为 {value}，"
                        "出现负值"
                    ),
                })

    # --------------------------------------------------------
    # Mole flow
    # --------------------------------------------------------

    mole_flow = stream.get(
        "mole_flow",
        {}
    )

    if isinstance(mole_flow, dict):

        for component, data in mole_flow.items():

            value = _numeric_value(data)

            if (
                value is not None
                and value < 0
            ):

                findings.append({
                    "level": "error",
                    "type": "negative_mole_flow",
                    "stream": stream_name,
                    "component": component,
                    "value": value,
                    "message": (
                        f"{component} "
                        f"摩尔流量为 {value}，"
                        "出现负值"
                    ),
                })

    # --------------------------------------------------------
    # Mole fraction
    # --------------------------------------------------------

    mole_fraction = stream.get(
        "mole_fraction",
        {}
    )

    fraction_sum = 0.0
    valid_fraction_count = 0

    if isinstance(mole_fraction, dict):

        for component, data in (
            mole_fraction.items()
        ):

            value = _numeric_value(data)

            if value is None:
                continue

            valid_fraction_count += 1
            fraction_sum += value

            if (
                value < 0
                or value > 1
            ):

                findings.append({
                    "level": "error",
                    "type": "invalid_mole_fraction",
                    "stream": stream_name,
                    "component": component,
                    "value": value,
                    "message": (
                        f"{component} 摩尔分率为 "
                        f"{value}，"
                        "不在 0~1 范围内"
                    ),
                })

    # --------------------------------------------------------
    # Fraction sum
    # --------------------------------------------------------

    if valid_fraction_count > 0:

        difference = abs(
            fraction_sum - 1.0
        )

        if difference > 0.01:

            findings.append({
                "level": "warning",
                "type": "fraction_sum_abnormal",
                "stream": stream_name,
                "value": fraction_sum,
                "message": (
                    f"摩尔分率总和为 "
                    f"{fraction_sum:.6f}，"
                    "明显偏离 1"
                ),
            })

    # --------------------------------------------------------
    # Empty data（组分数据整体缺失）
    # --------------------------------------------------------

    has_component_data = any(
        isinstance(
            stream.get(key),
            dict
        )
        and len(stream.get(key)) > 0
        for key in (
            "mole_fraction",
            "mole_flow",
            "mass_flow"
        )
    )

    if not has_component_data:

        findings.append({
            "level": "warning",
            "type": "empty_stream_data",
            "stream": stream_name,
            "message": (
                "流股缺少组分数据"
                "（mole_fraction / mole_flow / "
                "mass_flow 均为空）"
            ),
        })

    return findings


# ============================================================
# ② 整个流程的数据检查
# ============================================================

def check_process(process_data):
    """
    对整个 data_get 返回结果进行基础检查。

    参数：
        process_data
        即 data_get_process_tool_v2 返回的 dict

    返回：
        findings
    """

    findings = []

    if not isinstance(
        process_data,
        dict
    ):

        return [{
            "level": "error",
            "type": "invalid_process_data",
            "message": (
                "data_get 返回结果不是 dict"
            ),
        }]

    # --------------------------------------------------------
    # data_get 是否成功
    # --------------------------------------------------------

    if not process_data.get(
        "success",
        False
    ):

        return [{
            "level": "error",
            "type": "data_get_failed",
            "message": (
                "data_get 执行失败："
                + str(
                    process_data.get(
                        "error",
                        "未知错误"
                    )
                )
            ),
        }]

    streams = process_data.get(
        "streams",
        {}
    )

    if not isinstance(
        streams,
        dict
    ):

        findings.append({
            "level": "error",
            "type": "invalid_streams",
            "message": (
                "streams 数据不是 dict"
            ),
        })

        return findings

    # --------------------------------------------------------
    # 检查每个 Stream
    # --------------------------------------------------------

    for stream_name, stream in (
        streams.items()
    ):

        findings.extend(
            check_stream(
                stream_name,
                stream
            )
        )

    # --------------------------------------------------------
    # 检查 Block / Connection 基本一致性
    # --------------------------------------------------------

    blocks = process_data.get(
        "blocks",
        []
    )

    block_details = process_data.get(
        "block_details",
        []
    )

    connections = process_data.get(
        "connections",
        []
    )

    # Block detail 名称集合
    detail_names = set()

    if isinstance(
        block_details,
        list
    ):

        for detail in block_details:

            if not isinstance(
                detail,
                dict
            ):
                continue

            name = detail.get(
                "block"
            )

            if name:
                detail_names.add(
                    str(name)
                )

    elif isinstance(
        block_details,
        dict
    ):

        detail_names = {
            str(name)
            for name in block_details
        }

    # 检查 Block detail
    if isinstance(
        blocks,
        list
    ):

        for block in blocks:

            block_name = str(
                block
            )

            if (
                detail_names
                and block_name
                not in detail_names
            ):

                findings.append({
                    "level": "warning",
                    "type": "missing_block_detail",
                    "block": block_name,
                    "message": (
                        f"{block_name} "
                        "没有对应的 block_details"
                    ),
                })

    # --------------------------------------------------------
    # 检查 Connection 中出现的 Stream
    # --------------------------------------------------------

    stream_names = {
        str(name)
        for name in streams
    }

    if isinstance(
        connections,
        list
    ):

        for connection in connections:

            if not isinstance(
                connection,
                dict
            ):
                continue

            block_name = connection.get(
                "block",
                ""
            )

            for stream_name in (
                connection.get(
                    "inputs",
                    []
                )
            ):

                if (
                    str(stream_name)
                    not in stream_names
                ):

                    findings.append({
                        "level": "warning",
                        "type": "missing_input_stream",
                        "block": block_name,
                        "stream": str(
                            stream_name
                        ),
                        "message": (
                            f"{block_name} 的输入 "
                            f"{stream_name} "
                            "未在 streams 中找到"
                        ),
                    })

            for stream_name in (
                connection.get(
                    "outputs",
                    []
                )
            ):

                if (
                    str(stream_name)
                    not in stream_names
                ):

                    findings.append({
                        "level": "warning",
                        "type": "missing_output_stream",
                        "block": block_name,
                        "stream": str(
                            stream_name
                        ),
                        "message": (
                            f"{block_name} 的输出 "
                            f"{stream_name} "
                            "未在 streams 中找到"
                        ),
                    })

    # --------------------------------------------------------
    # ds: 模拟运行状态检查（data_get 返回 simulation_status）
    # --------------------------------------------------------

    simulation_status = process_data.get(
        "simulation_status",
        {},
    )

    if isinstance(
        simulation_status,
        dict,
    ):

        status = simulation_status.get(
            "status",
        )

        error_count = simulation_status.get(
            "error_count",
            0,
        )

        errors = simulation_status.get(
            "errors",
            [],
        )

        if status == "error" or error_count:

            detail = (
                "；".join(
                    str(x)
                    for x in (
                        errors
                        if isinstance(errors, list)
                        else []
                    )
                )
            )

            if detail:
                detail = "：" + detail

            findings.append({
                "level": "error",
                "type": "simulation_error",
                "error_count": error_count,
                "message": (
                    "Aspen 模拟存在报错"
                    f"（{error_count} 条）"
                    + detail
                ),
            })

        elif status == "ok":

            findings.append({
                "level": "info",
                "type": "simulation_ok",
                "message": "Aspen 模拟运行正常，无报错",
            })

    return findings


# ============================================================
# ③ 查找组件
# ============================================================

def find_component(
    process_data,
    component
):
    """
    在所有物流中寻找指定组分。

    例如：

        find_component(data, "环己烷")

    返回：

        [
            {
                "stream": "S5",
                "mole_fraction": 0.473,
                ...
            }
        ]
    """

    results = []

    if not component:
        return results

    streams = process_data.get(
        "streams",
        {}
    )

    if not isinstance(
        streams,
        dict
    ):
        return results

    target = str(
        component
    ).lower()

    for stream_name, stream in (
        streams.items()
    ):

        if not isinstance(
            stream,
            dict
        ):
            continue

        mole_fraction = stream.get(
            "mole_fraction",
            {}
        )

        mole_flow = stream.get(
            "mole_flow",
            {}
        )

        mass_flow = stream.get(
            "mass_flow",
            {}
        )

        # ----------------------------------------------------
        # 找实际组件名
        # ----------------------------------------------------

        fraction_name = None
        mole_flow_name = None
        mass_flow_name = None

        if isinstance(
            mole_fraction,
            dict
        ):

            fraction_name = _find_key(
                target,
                list(
                    mole_fraction.keys()
                )
            )

        if isinstance(
            mole_flow,
            dict
        ):

            mole_flow_name = _find_key(
                target,
                list(
                    mole_flow.keys()
                )
            )

        if isinstance(
            mass_flow,
            dict
        ):

            mass_flow_name = _find_key(
                target,
                list(
                    mass_flow.keys()
                )
            )

        # 没找到
        if (
            fraction_name is None
            and mole_flow_name is None
            and mass_flow_name is None
        ):
            continue

        # ----------------------------------------------------
        # Mole fraction
        # ----------------------------------------------------

        fraction_value = None
        fraction_unit = ""

        if fraction_name is not None:

            data = mole_fraction[
                fraction_name
            ]

            fraction_value = (
                _numeric_value(data)
            )

            fraction_unit = _unit(
                data
            )

        # ----------------------------------------------------
        # Mole flow
        # ----------------------------------------------------

        mole_flow_value = None
        mole_flow_unit = ""

        if mole_flow_name is not None:

            data = mole_flow[
                mole_flow_name
            ]

            mole_flow_value = (
                _numeric_value(data)
            )

            mole_flow_unit = _unit(
                data
            )

        # ----------------------------------------------------
        # Mass flow
        # ----------------------------------------------------

        mass_flow_value = None
        mass_flow_unit = ""

        if mass_flow_name is not None:

            data = mass_flow[
                mass_flow_name
            ]

            mass_flow_value = (
                _numeric_value(data)
            )

            mass_flow_unit = _unit(
                data
            )

        results.append({

            "component": (
                fraction_name
                or mole_flow_name
                or mass_flow_name
            ),

            "stream": str(
                stream_name
            ),

            "mole_fraction": (
                fraction_value
            ),

            "mole_fraction_unit": (
                fraction_unit
            ),

            "mole_flow": (
                mole_flow_value
            ),

            "mole_flow_unit": (
                mole_flow_unit
            ),

            "mass_flow": (
                mass_flow_value
            ),

            "mass_flow_unit": (
                mass_flow_unit
            ),
        })

    # --------------------------------------------------------
    # 按摩尔分率从高到低排序
    # --------------------------------------------------------

    results.sort(
        key=lambda item:
            item["mole_fraction"]
            if item["mole_fraction"] is not None
            else -float("inf"),

        reverse=True
    )

    return results


# ============================================================
# ④ 比较两个 Stream
# ============================================================

def compare_streams(
    process_data,
    stream_a,
    stream_b
):
    """
    比较两个物流的关键参数和组分。

    例如：

        S4 → S5

    可以得到：

        甲苯：19.75% → 0.48%
        环己烷：0 → 47.30%
        CH4：0 → 47.30%
    """

    streams = process_data.get(
        "streams",
        {}
    )

    if not isinstance(
        streams,
        dict
    ):
        return {
            "success": False,
            "error": "streams 数据无效"
        }

    if stream_a not in streams:

        return {
            "success": False,
            "error": (
                f"找不到物流 {stream_a}"
            )
        }

    if stream_b not in streams:

        return {
            "success": False,
            "error": (
                f"找不到物流 {stream_b}"
            )
        }

    a = streams[
        stream_a
    ]

    b = streams[
        stream_b
    ]

    result = {

        "success": True,

        "from_stream": stream_a,

        "to_stream": stream_b,

        "temperature": {},

        "pressure": {},

        "vapor_fraction": {},

        "components": [],
    }

    # --------------------------------------------------------
    # 基础参数
    # --------------------------------------------------------

    for key in (
        "temperature",
        "pressure",
        "vapor_fraction"
    ):

        a_data = a.get(
            key
        )

        b_data = b.get(
            key
        )

        a_value = _numeric_value(
            a_data
        )

        b_value = _numeric_value(
            b_data
        )

        result[key] = {

            "from": a_value,

            "to": b_value,

            "difference": (
                b_value - a_value
                if (
                    a_value is not None
                    and b_value is not None
                )
                else None
            ),

            "from_unit": _unit(
                a_data
            ),

            "to_unit": _unit(
                b_data
            ),
        }

    # --------------------------------------------------------
    # 组分比较
    # --------------------------------------------------------

    a_fraction = a.get(
        "mole_fraction",
        {}
    )

    b_fraction = b.get(
        "mole_fraction",
        {}
    )

    if not isinstance(
        a_fraction,
        dict
    ):
        a_fraction = {}

    if not isinstance(
        b_fraction,
        dict
    ):
        b_fraction = {}

    # 大小写不敏感的名称映射
    a_map = {
        str(name).lower(): name
        for name in a_fraction
    }

    b_map = {
        str(name).lower(): name
        for name in b_fraction
    }

    component_keys = (
        set(a_map)
        | set(b_map)
    )

    for key in component_keys:

        a_name = a_map.get(
            key
        )

        b_name = b_map.get(
            key
        )

        a_data = (
            a_fraction[a_name]
            if a_name is not None
            else None
        )

        b_data = (
            b_fraction[b_name]
            if b_name is not None
            else None
        )

        a_value = (
            _numeric_value(a_data)
            if a_data is not None
            else 0.0
        )

        b_value = (
            _numeric_value(b_data)
            if b_data is not None
            else 0.0
        )

        # 如果数据本身不存在，
        # 才使用 None；否则缺失组分在比较时视作 0。
        if a_data is None:
            a_value = 0.0

        if b_data is None:
            b_value = 0.0

        actual_name = (
            a_name
            or b_name
            or key
        )

        result["components"].append({

            "component": actual_name,

            "from": a_value,

            "to": b_value,

            "difference": (
                b_value - a_value
            ),

            "absolute_change": abs(
                b_value - a_value
            ),
        })

    # 按变化绝对值排序
    result["components"].sort(
        key=lambda item:
            item["absolute_change"],
        reverse=True
    )

    return result


# ============================================================
# ⑤ 自动寻找明显的前后变化
# ============================================================

def detect_stream_changes(
    process_data,
    threshold=0.05
):
    """
    自动寻找 connections 中相邻 Block 的
    输入/输出物流变化。

    threshold：
        摩尔分率绝对变化超过多少，
        才认为值得关注。

    默认：
        0.05 = 5 个百分点

    注意：
        这里只负责发现“数字变化”。

        不判断：
        “这是正常反应还是异常”。

        化工意义交给 Agent。
    """

    results = []

    connections = process_data.get(
        "connections",
        []
    )

    if not isinstance(
        connections,
        list
    ):
        return results

    for connection in connections:

        if not isinstance(
            connection,
            dict
        ):
            continue

        block = str(
            connection.get(
                "block",
                ""
            )
        )

        inputs = connection.get(
            "inputs",
            []
        )

        outputs = connection.get(
            "outputs",
            []
        )

        if not isinstance(
            inputs,
            list
        ):
            inputs = []

        if not isinstance(
            outputs,
            list
        ):
            outputs = []

        # ----------------------------------------------------
        # 对一个 Block 的输入/输出做比较
        # ----------------------------------------------------

        for input_stream in inputs:

            for output_stream in outputs:

                comparison = compare_streams(
                    process_data,
                    str(input_stream),
                    str(output_stream)
                )

                if not comparison.get(
                    "success",
                    False
                ):
                    continue

                significant_components = [

                    item

                    for item in comparison[
                        "components"
                    ]

                    if item[
                        "absolute_change"
                    ] >= threshold

                ]

                if significant_components:

                    results.append({

                        "block": block,

                        "from_stream": str(
                            input_stream
                        ),

                        "to_stream": str(
                            output_stream
                        ),

                        "significant_components":
                            significant_components,
                    })

    return results


# ============================================================
# ⑥ 主分析函数
# ============================================================

def _coerce_process_data(process_data):
    """
    把 Agent Tool 传来的参数规整成 dict。

    支持：
        dict                   → 原样
        str（JSON 字符串）      → json.loads
        bytes / bytearray      → 解码后 json.loads

    返回：
        (dict, None) 正常
        (None, 错误消息) 无法规整
    """

    if isinstance(process_data, dict):
        return process_data, None

    if isinstance(process_data, (bytes, bytearray)):

        try:

            text = bytes(process_data).decode("utf-8")

        except Exception as e:

            return (
                None,
                "process_data 解码失败：" + str(e),
            )

        return _coerce_process_data(text)

    if isinstance(process_data, str):

        text = process_data.strip()

        if not text:
            return (
                None,
                "process_data 是空字符串",
            )

        try:

            data = json.loads(text)

        except Exception as e:

            return (
                None,
                "process_data 不是合法 JSON：" + str(e),
            )

        if not isinstance(data, dict):
            return (
                None,
                "process_data JSON 不是对象（dict）",
            )

        return data, None

    return (
        None,
        "process_data 类型不支持："
        + type(process_data).__name__,
    )


def analyze(
    process_data,
    component=None,
    change_threshold=0.05
):
    """
    ChemMate V1 薄分析层统一入口。

    参数：

        process_data
            data_get_process_tool_v2 返回的数据。
            接受 dict 或 JSON 字符串
            （Agent Tool 按字符串传参时无需转换）。

        component
            可选。例如：
                "环己烷"

        change_threshold
            组分变化阈值。默认 5 个百分点。

    返回：

        {
            "success": True,
            "summary": {...},
            "findings": [...],
            "component_tracking": [...],
            "stream_changes": [...]
        }

        数据源本身失败 / 参数无法解析时：
        {
            "success": False,
            "error": "...",
            "findings": [...]
        }
    """

    # --------------------------------------------------------
    # 0. 输入规整（dict / JSON 字符串 / 其他）
    # --------------------------------------------------------

    data, coerce_error = (
        _coerce_process_data(
            process_data
        )
    )

    if coerce_error is not None:

        return {

            "success": False,

            "error": coerce_error,

            "findings": [{

                "level": "error",

                "type": "invalid_process_data",

                "message": coerce_error,

            }],
        }

    # --------------------------------------------------------
    # 1. data_get 本身失败 → 短路
    # --------------------------------------------------------

    if not data.get(
        "success",
        False
    ):

        message = (
            "data_get 执行失败："
            + str(
                data.get(
                    "error",
                    "未知错误"
                )
            )
        )

        return {

            "success": False,

            "error": data.get(
                "error",
                "未知错误"
            ),

            "findings": [{

                "level": "error",

                "type": "data_get_failed",

                "message": message,

            }],
        }

    # --------------------------------------------------------
    # 2. 基础检查
    # --------------------------------------------------------

    findings = check_process(
        data
    )

    # --------------------------------------------------------
    # 3. 统计信息
    # --------------------------------------------------------

    streams = data.get(
        "streams",
        {}
    )

    blocks = data.get(
        "blocks",
        []
    )

    connections = data.get(
        "connections",
        []
    )

    summary = {

        "stream_count":
            len(streams)
            if isinstance(
                streams,
                dict
            )
            else 0,

        "block_count":
            len(blocks)
            if isinstance(
                blocks,
                list
            )
            else 0,

        "connection_count":
            len(connections)
            if isinstance(
                connections,
                list
            )
            else 0,

        "error_count":
            sum(
                1
                for item in findings
                if item.get(
                    "level"
                ) == "error"
            ),

        "warning_count":
            sum(
                1
                for item in findings
                if item.get(
                    "level"
                ) == "warning"
            ),
    }

    # --------------------------------------------------------
    # 组分追踪
    # --------------------------------------------------------

    component_tracking = []

    if component:

        component_tracking = (
            find_component(
                data,
                component
            )
        )

    # --------------------------------------------------------
    # 前后变化
    # --------------------------------------------------------

    stream_changes = (
        detect_stream_changes(
            data,
            threshold=change_threshold
        )
    )

    # --------------------------------------------------------
    # 最终结果
    # --------------------------------------------------------

    return {

        "success": True,

        "summary": summary,

        "findings": findings,

        "component_tracking":
            component_tracking,

        "stream_changes":
            stream_changes,
    }


# ============================================================
# ⑦ Agent Tool 注册入口（字符串参数友好）
# ============================================================

def analyze_process(
    process_data,
    component=None,
    change_threshold=0.05
):
    """
    ChemMate V1 薄分析层 —— Agent Tool 注册入口。

    与 analyze 完全等价，但按 Agent Tool
    “所有 Tool 都必须接收字符串参数”的约定设计：

        analyze_process(
            '<data_get 返回的完整 JSON 字符串>',
            component="环己烷",
        )

    也接受 dict（供 Python 内部直接调用），
    内部统一由 _coerce_process_data 规整。

    返回结构同 analyze：

        {
            "success": True,
            "summary": {...},
            "findings": [...],
            "component_tracking": [...],
            "stream_changes": [...]
        }
    """

    return analyze(
        process_data,
        component=component,
        change_threshold=change_threshold,
    )


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    print(
        "ChemMate V1 analyzer.py"
    )

    print(
        "这是分析工具模块，"
        "需要由 Agent / 主程序传入 "
        "data_get_process_tool_v2 的返回结果。"
    )

    print(
        "Agent Tool 注册用：analyze_process("
        "json_str, component=..., change_threshold=...)"
    )