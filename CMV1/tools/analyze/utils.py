# ============================================================
# 基础工具
# ============================================================




import json

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

