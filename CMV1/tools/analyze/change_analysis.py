import json


#============================================================
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

