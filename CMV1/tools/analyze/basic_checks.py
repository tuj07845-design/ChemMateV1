# ============================================================
# ① 基础数据检查
# ============================================================



import json

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
                        "type": "missing_output_stream"
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
