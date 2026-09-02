# ============================================================
# ③ 查找组件
# ============================================================



import json

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
