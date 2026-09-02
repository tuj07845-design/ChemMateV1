import os
import json
import win32com.client as win32



# ============================================================
# 七、小工具函数（从 v1 复制，保持不变）
# ============================================================

def read_value(output, variable_name):
    """
    读取一个 Aspen 普通数据节点。

    例如：TEMP_OUT / PRES_OUT / VFRAC_OUT

    返回：
        { "value": 数值, "unit": 单位 }
    """

    try:

        node = (
            output
            .Elements(variable_name)
            .Elements("MIXED")
        )

        value = node.Value

        try:

            unit = node.UnitString

        except Exception:

            unit = ""

        return {

            "value": value,

            "unit": unit,

        }

    except Exception:

        return {

            "value": None,

            "unit": "",

        }


def read_component_data(output, variable_name):
    """
    读取 Aspen 组分数据。

    例如：MASSFLOW / MOLEFLOW / MOLEFRAC

    返回：
        {
            "组件1": { "value": xxx, "unit": "kg/hr" },
            ...
        }
    """

    data = {}

    try:

        node = (
            output
            .Elements(variable_name)
            .Elements("MIXED")
        )

        for component in node.Elements:

            name = component.Name

            value = component.Value

            try:

                unit = component.UnitString

            except Exception:

                unit = ""

            data[name] = {

                "value": value,

                "unit": unit,

            }

    except Exception:

        pass

    return data


# ============================================================
# ds: 模拟状态 / 报错读取（原 data_get 缺失，Agent 因此查不到报错）
# ============================================================

def read_simulation_status(Data):
    """
    ds: 读取 Aspen 模拟运行状态与报错信息。

    数据来源（Data\\Results Summary\\Run-Status\\Output 节点）：
        PER_ERROR          = 报错条数（>0 说明有设备计算报错）
        PER_ERROR\1..N     = 报错文本（含出错设备名，如 B8）
        TOTSTAT / UOSSTAT  = 总状态码 / 单元操作状态码（原样返回供参考）

    返回：
        {
            "status": "error" | "ok" | "unknown",
            "error_count": 0,
            "errors": ["..."],
            "status_codes": {"TOTSTAT": 1, "UOSSTAT": 1, "UOSSTAT2": 9, "ITSTAT": 0},
        }

    说明：
        - 只做确定性读取，不判读状态码含义（交给 Agent 解释）；
        - 任何一步读不到都不抛异常，status 回落为 unknown。
    """

    result = {
        "status": "unknown",
        "error_count": 0,
        "errors": [],
        "status_codes": {},
    }

    try:

        run_status_output = (
            Data
            .Elements("Results Summary")
            .Elements("Run-Status")
            .Elements("Output")
        )

        # ---------- 状态码（原样收集，读不到就跳过） ----------

        for code_name in (
            "TOTSTAT",
            "UOSSTAT",
            "UOSSTAT2",
            "ITSTAT",
            "RSTAT",
            "SSTAT",
        ):

            try:

                code_node = (
                    run_status_output
                    .Elements(code_name)
                )

                result["status_codes"][code_name] = (
                    code_node.Value
                )

            except Exception:

                pass

        # ---------- 报错文本（PER_ERROR） ----------

        try:

            per_error_node = (
                run_status_output
                .Elements("PER_ERROR")
            )

            try:

                error_count = int(
                    per_error_node.Value
                )

            except Exception:

                error_count = 0

            result["error_count"] = error_count

            errors = []

            # ds: PER_ERROR 的 N 是"组"数，一组错误文本可能跨多行
            # ds: （PER_ERROR\1..N 连续行），所以连续枚举直到读不到为止
            for i in range(1, 50):

                try:

                    line = (
                        run_status_output
                        .Elements("PER_ERROR")
                        .Elements(str(i))
                        .Value
                    )

                except Exception:

                    break

                text = str(line).strip()

                if text:
                    errors.append(text)

            # 收集到几条算几条；如果 PER_ERROR 声称有错但没读到文本，
            # 保留错误状态但 errors 列表可为空
            result["errors"] = errors

            if error_count > 0:
                result["status"] = "error"

            elif result["status_codes"]:
                result["status"] = "ok"

        except Exception:

            # 没有 PER_ERROR 节点：无法确定，保持 unknown
            pass

    except Exception:

        pass

    return result

