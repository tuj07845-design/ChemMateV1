# ============================================================
# ⑥ 主分析函数
# ============================================================

from .utils import _number, _value, _unit, _numeric_value, _find_key, _stream_summary
from .basic_checks import check_process
from .component_track import find_component
from .change_analysis import compare_streams, detect_stream_changes


import json

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

