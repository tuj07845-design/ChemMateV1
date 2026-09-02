import os
import json
import win32com.client as win32

def get_block_real_type(flowsheet_input, block_name):
    """
    读取设备的真实类型名称。

    参数：
        flowsheet_input :
            \\Data\\Flowsheet\\Section\\GLOBAL\\Input 节点

        block_name :
            设备名，例如 "B5"

    返回：
        {
            "real_type":  "RStoic",   ← 模型显示名（优先）
            "type_code":  "RSTOIC",   ← 大写类型码
        }

    原理：
        MDLTYPE\\<设备名> 和 BLKTYPE\\<设备名> 是 Aspen 记录
        "每个设备用的是什么模型"的权威节点。
    """

    result = {
        "real_type": "",
        "type_code": "",
    }

    # ---------- 1. 优先读 MDLTYPE（显示名，如 RStoic） ----------

    try:

        node = (
            flowsheet_input
            .Elements("MDLTYPE")
            .Elements(block_name)
        )

        result["real_type"] = str(node.Value)

    except Exception:

        pass

    # ---------- 2. 读 BLKTYPE（大写类型码，如 RSTOIC） ----------

    try:

        node = (
            flowsheet_input
            .Elements("BLKTYPE")
            .Elements(block_name)
        )

        result["type_code"] = str(node.Value)

    except Exception:

        pass

    return result


# ============================================================
# 三、递归收集设备 Input 参数（该类型特有的数据）
# ============================================================

def collect_block_parameters(node, path="", result=None, depth=0, max_depth=8):
    """
    递归收集一个设备 Input 节点下的所有"有值"参数。

    参数：
        node      : \\Data\\Blocks\\B1\\Input 节点（或它的任意子节点）
        path      : 当前走过的路径（相对 Input）
        result    : 收集结果字典（函数间共享）
        depth     : 当前深度
        max_depth : 最深探到第几层（防递归太深）

    返回：
        {
            "参数路径": {
                "value": 值,
                "unit":  单位
            },
            ...
        }

    例：
        {
            "TEMP":        {"value": 300.0, "unit": "C"},
            "PRES":        {"value": 30.0,  "unit": "bar"},
            "Reactions\\R-1\\STOIC\\1": {"value": ..., "unit": ""}
        }
    """

    if result is None:

        result = {}

    try:

        # ---------- 遍历当前节点的所有子节点 ----------

        children = node.Elements

        count = children.Count

        # Aspen 的集合索引从 1 开始，先探测一下更稳妥
        try:
            children.Item(0)
            start = 0
        except Exception:
            start = 1

        for i in range(start, start + count):

            child = children.Item(i)

            # 子节点的名字
            try:
                name = child.Name
            except Exception:
                continue

            # 拼出相对路径
            child_path = (
                path + "\\" + name if path else name
            )

            # ---------- 尝试读取这个节点的值 ----------

            value = None

            has_value = False

            try:

                value = child.Value

                # 过滤掉空值 / COM 对象等无意义的值
                text = str(value)

                if (
                    value is not None
                    and text.strip() != ""
                    and "COMObject" not in text
                ):

                    has_value = True

            except Exception:

                pass

            # ---------- 有值就保存 ----------

            if has_value:

                # 尝试读单位（不是所有节点都有单位）
                try:

                    unit = str(child.UnitString)

                except Exception:

                    unit = ""

                result[child_path] = {

                    "value": value,

                    "unit": unit,

                }

            # ---------- 继续往深处递归 ----------

            if depth < max_depth:

                try:

                    sub = child.Elements

                    if sub.Count > 0:

                        collect_block_parameters(
                            child,
                            child_path,
                            result,
                            depth + 1,
                            max_depth,
                        )

                except Exception:

                    pass

    except Exception:

        pass

    return result


# ============================================================
# 四、根据类型名称挑选"招牌参数"
# ============================================================

def pick_key_parameters(real_type, all_parameters):
    """
    根据设备类型名称，从全部参数里挑选该类型的招牌参数。

    参数：
        real_type     : 设备真实类型名，例如 "RadFrac"
        all_parameters: collect_block_parameters 的返回值

    返回：
        {
            "参数名": {
                "value": 值,
                "unit":  单位,
                "description": "中文说明"
            },
            ...
        }

    挑选规则：
        1. 先按【类型知识库】里的 key_parameters 名单精确匹配；
        2. 再按"参数名字特征"自动补挑（含 TEMP/PRES/DUTY 等
           关键字的参数），保证知识库没覆盖到的类型也有数据；
        3. 最后按"该类型特有的参数"（名字在知识库名单里）
           补充。
    """

    key_params = {}

    # ---------- 1. 知识库精确匹配 ----------

    knowledge = TYPE_KNOWLEDGE.get(
        real_type,
        {}
    )

    wanted = knowledge.get(
        "key_parameters",
        {}
    )

    for param_name, description in wanted.items():

        for full_path, item in all_parameters.items():

            # 匹配参数名（路径的最后一段）
            short_name = full_path.split("\\")[-1]

            if short_name == param_name:

                key_params[full_path] = {

                    "value": item["value"],

                    "unit": item["unit"],

                    "description": description,

                }

                break

    # ---------- 2. 自动特征匹配（知识库没覆盖到也能用） ----------

    # 常见"招牌"关键字：温度、压力、热负荷、流量、效率……
    hot_keywords = [
        "TEMP", "PRES", "DUTY",
        "FLOW", "EFF", "AREA",
        "RR", "NSTAGE", "VFRAC",
        "PDROP", "POWER",
    ]

    for full_path, item in all_parameters.items():

        # 已经在知识库挑中的跳过
        if full_path in key_params:
            continue

        short_name = full_path.split("\\")[-1]

        upper_name = short_name.upper()

        # 跳过容差/检查/校正类参数（*_TOL *_CHK *_CORR）和纯 YES/NO 开关，
        # 减少自动识别的噪音
        if "TOL" in upper_name:
            continue

        if "CHK" in upper_name:
            continue

        if "CORR" in upper_name:
            continue

        try:
            if str(item["value"]).strip().upper() in ("YES", "NO"):
                continue
        except Exception:
            pass

        for keyword in hot_keywords:

            if keyword in upper_name:

                key_params[full_path] = {

                    "value": item["value"],

                    "unit": item["unit"],

                    "description": "自动识别（含关键字 " + keyword + "）",

                }

                break

    return key_params


# ============================================================
# 五、单个设备：类型 + 类型特有数据
# ============================================================

def get_block_type_data(block_node, block_name, flowsheet_input):
    """
    综合获取一个设备的：
        1. 真实类型名称
        2. 该类型特有的数据（招牌参数 + 全部参数）

    参数：
        block_node     : \\Data\\Blocks\\<设备名> 节点
        block_name     : 设备名，例如 "B5"
        flowsheet_input: \\Data\\Flowsheet\\Section\\GLOBAL\\Input 节点

    返回：
        {
            "block":          "B5",
            "real_type":      "RStoic",
            "type_code":      "RSTOIC",
            "category":       "化学计量反应器",
            "key_parameters": {...},   ← 招牌参数（带中文说明）
            "all_parameters_count": 42,
            "all_parameters": {...}    ← 全部有值参数
        }
    """

    # ---------- 1. 真实类型名称 ----------

    type_info = get_block_real_type(
        flowsheet_input,
        block_name,
    )

    real_type = type_info["real_type"]

    type_code = type_info["type_code"]

    # ---------- 2. 类型知识库 → 中文类别 ----------

    category = DEFAULT_CATEGORY

    if real_type in TYPE_KNOWLEDGE:

        category = TYPE_KNOWLEDGE[real_type]["category"]

    elif type_code in TYPE_KNOWLEDGE:

        category = TYPE_KNOWLEDGE[type_code]["category"]

    # ---------- 3. 收集该类型特有的参数 ----------

    all_parameters = {}

    try:

        input_node = block_node.Elements("Input")

        all_parameters = collect_block_parameters(
            input_node
        )

    except Exception:

        pass

    # ---------- 4. 挑选招牌参数 ----------

    key_parameters = pick_key_parameters(
        real_type,
        all_parameters,
    )

    # ---------- 5. 组装返回 ----------

    return {

        "block": block_name,

        "real_type": real_type,

        "type_code": type_code,

        "category": category,

        "key_parameters": key_parameters,

        "all_parameters_count": len(all_parameters),

        "all_parameters": all_parameters,

    }

