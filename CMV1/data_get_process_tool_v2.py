# -*- coding: utf-8 -*-
"""
============================================================
 ChemMate V1
 data_get_process_tool_v2.py
（data_get_process_tool.py 的增强版，原文件未改动）
============================================================

 本文件在原有 data_get_process 基础上，新增两大能力：

 ┌────────────────────────────────────────────────────────┐
 │ ① 获取设备的【真实类型名称】                            │
 │                                                          │
 │    来源：\\Data\\Flowsheet\\Section\\GLOBAL\\Input\\     │
 │          MDLTYPE\\<设备名>   → 模型显示名，如 RStoic     │
 │          BLKTYPE\\<设备名>   → 大写类型码，如 RSTOIC     │
 │                                                          │
 │    例：本机 "10万吨环己烷.bkp" 中                        │
 │        B1=Pump  B2=Compr  B3=Mixer  B4/B6=Heater        │
 │        B5=RStoic  B7=Flash2  B8=RadFrac                 │
 └────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────┐
 │ ② 根据类型名称获取【该类型特有的数据】                  │
 │                                                          │
 │    来源：\\Data\\Blocks\\<设备名>\\Input\\...             │
 │          每个类型在 Input 下都有自己特有的参数群：        │
 │          塔(RadFrac) → 回流比 BASIS_RR、塔径 CA_DIAM…    │
 │          加热器(Heater) → 出口温度 TEMP、压力 PRES…      │
 │                                                          │
 │    做法：递归收集 Input 下全部有值参数（all_parameters） │
 │          + 内置【类型知识库】挑选招牌参数                │
 │          （key_parameters，带中文说明）                  │
 └────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────┐
 │ ③ 完整流程信息 Tool（供 Agent 调用）                    │
 │                                                          │
 │    返回 JSON 完全兼容原 data_get_process 的所有字段，    │
 │    并新增 "block_details" 字段：                         │
 │      每个设备的类型 + 招牌参数 + 全部参数                │
 └────────────────────────────────────────────────────────┘

 设计参考：
   开源 AspenPlus-MCP-Server 与 Aspen_Co-pilot 的核心思路——
   Aspen Plus 树中一切数据都是 \\Data\\... 路径下的节点，
   按节点路径读取即可；设备类型名是理解设备的关键索引。
"""

import os
import json
import win32com.client as win32


# ============================================================
# 一、类型知识库
# ============================================================
# 【作用】拿到设备真实类型名（如 RStoic）后，查这个字典就能知道：
#    - 中文名 / 类别（category）
#    - 该类型最值得读的"招牌参数"（参数名 → 中文说明）
#
# 注意：参数名如果模型里不存在，会在挑选时自动跳过，
#       不会报错；全部参数仍可从 all_parameters 拿到。

TYPE_KNOWLEDGE = {

    "Pump": {
        "category": "泵",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "EFF": "效率",
            "POWER_REQ": "所需功率",
            "PRES_RATIO": "增压比",
            "VFRAC": "出口气相分率",
            "TEMP": "出口温度",
        },
    },

    "Compr": {
        "category": "压缩机",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "PRES_RATIO": "压缩比",
            "EFF": "效率",
            "POWER_REQ": "轴功率",
            "TEMP": "出口温度",
            "PMODEL": "性能模型",
        },
    },

    "Mixer": {
        "category": "混合器",
        "key_parameters": {
            "NPHASE": "相数",
            "TEMP": "出口温度",
            "PRES": "出口压力",
            "DUTY": "热负荷",
            "BLKOPFREWAT": "自由水选项",
        },
    },

    "Heater": {
        "category": "加热器/冷却器",
        "key_parameters": {
            "TEMP": "出口温度",
            "PRES": "出口压力",
            "DUTY": "热负荷",
            "VFRAC": "出口气相分率",
            "HEATOPT": "热负荷选项",
            "SPEC_OPT": "规定选项(TP/TQ)",
            "DELT": "温差",
        },
    },

    "RStoic": {
        "category": "化学计量反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "HEATOPT": "热负荷选项",
            "VFRAC": "出口气相分率",
            "STOIC": "化学计量式",
        },
    },

    "Flash2": {
        "category": "两相闪蒸罐",
        "key_parameters": {
            "TEMP": "闪蒸温度",
            "PRES": "闪蒸压力",
            "DUTY": "热负荷",
            "VFRAC": "气相分率",
            "SPEC_OPT": "规定选项",
            "NPHASE": "相数",
        },
    },

    "RadFrac": {
        "category": "严格精馏塔",
        "key_parameters": {
            "BASIS_RR": "回流比",
            "BASIS_D": "馏出物量",
            "NSTAGE": "塔板数",
            "BEG_STAGES": "进料板",
            "CONDENSER": "冷凝器",
            "REBOILER": "再沸器",
            "ALGORITHM": "算法",
            "CALC_MODE": "计算模式",
            "CA_DIAM": "塔径",
            "ABSORBER": "是否吸收塔",
            "BASIS_B": "塔底采出量",
            "TOP_PRES": "塔顶压力",
            "BOT_PRES": "塔底压力",
        },
    },

    "HeatX": {
        "category": "换热器",
        "key_parameters": {
            "AREA": "换热面积",
            "DUTY": "热负荷",
            "LMTD": "对数平均温差",
            "CALC_MODE": "计算模式",
            "HOT_TEMP": "热流出口温度",
            "COLD_TEMP": "冷流出口温度",
        },
    },

    "DSTWU": {
        "category": "简捷精馏塔",
        "key_parameters": {
            "RR": "回流比",
            "NSTAGE": "理论板数",
            "LIGHT_KEY": "轻关键组分",
            "HEAVY_KEY": "重关键组分",
            "CONDENSER": "冷凝器类型",
        },
    },

    "RCSTR": {
        "category": "连续搅拌反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "HEATOPT": "热负荷选项",
            "VOLUME": "反应器体积",
            "VFRAC": "出口气相分率",
        },
    },

    "RPlug": {
        "category": "平推流反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "LENGTH": "管长",
            "DIAMETER": "管径",
        },
    },

    "RGibbs": {
        "category": "吉布斯反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "VFRAC": "出口气相分率",
        },
    },

    "RYield": {
        "category": "收率反应器",
        "key_parameters": {
            "TEMP": "反应温度",
            "PRES": "反应压力",
            "DUTY": "热负荷",
            "YIELD": "收率",
        },
    },

    "Valve": {
        "category": "阀门",
        "key_parameters": {
            "DISCHARGE_P": "出口压力",
            "PDROP": "压降",
            "CV": "流量系数",
            "PERCENT_OPEN": "开度",
        },
    },

    "Sep": {
        "category": "分离器",
        "key_parameters": {
            "SPLIT_FRAC": "分离分率",
            "TEMP": "温度",
            "PRES": "压力",
        },
    },

}

# 类别兜底：知识库里没有的类型，统一归为"其他"
DEFAULT_CATEGORY = "其他"


# ============================================================
# 二、获取设备真实类型名称
# ============================================================

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


# ============================================================
# 六、主流程：完整读取 Aspen 流程信息（增强版）
# ============================================================

def data_get_process(file_path):
    """
    ChemMate V1 - Process Data Tool（v2 增强版）

    一次读取 Aspen 模型中的：

    1. 全部 Stream 数据
        - temperature / pressure / vapor_fraction
        - mass_flow / mole_flow / mole_fraction

    2. 全部 Block + 【真实类型名称】+【类型特有数据】

    3. Block 与 Stream 的连接关系

    返回：
        一个完整的 Aspen 流程数据结构（JSON 字典，可直接给 Agent）
        相比 v1 新增字段：block_details
    """

    print("\n========================================")
    print("ChemMate V1 - Data Get Process (v2)")
    print("========================================")

    print("\n收到 Aspen 文件路径：")
    print(file_path)

    # ========================================================
    # 1. 检查路径
    # ========================================================

    if not file_path:

        return {

            "success": False,

            "error": "没有收到 Aspen 文件路径",

        }

    if not os.path.exists(file_path):

        return {

            "success": False,

            "error": "Aspen 文件不存在：" + file_path,

        }

    AspenSimulation = None

    try:

        # ====================================================
        # 2. 启动 Aspen
        # ====================================================

        print("\n正在启动 Aspen Plus...")

        AspenSimulation = (
            win32.gencache.EnsureDispatch(
                "Apwn.Document"
            )
        )

        # ====================================================
        # 3. 加载 Aspen 文件
        # ====================================================

        print("正在加载 Aspen 文件...")

        AspenSimulation.InitFromArchive2(
            os.path.abspath(file_path)
        )

        AspenSimulation.Visible = True

        print("Aspen 文件加载成功！")

        # ====================================================
        # 4. 获取 Data 节点
        # ====================================================

        Data = (
            AspenSimulation
            .Tree
            .Elements("Data")
        )

        # ====================================================
        # 5. 获取全部 Streams
        # ====================================================

        STRM = Data.Elements("Streams")

        print("\nStreams 节点获取成功！")

        all_streams = {}

        print("\n========================================")
        print("开始读取全部 Stream")
        print("========================================")

        for Stream in STRM.Elements:

            stream_name = Stream.Name

            print("\n----------------------------------------")
            print("当前 Stream：", stream_name)
            print("----------------------------------------")

            # ---------- 获取 Output ----------

            try:

                Output = Stream.Elements("Output")

            except Exception as e:

                print("Output 获取失败：", e)

                continue

            # ---------- 读取各数据 ----------

            temperature = read_value(Output, "TEMP_OUT")
            pressure = read_value(Output, "PRES_OUT")
            vapor_fraction = read_value(Output, "VFRAC_OUT")

            mass_flow = read_component_data(Output, "MASSFLOW")
            mole_flow = read_component_data(Output, "MOLEFLOW")
            mole_fraction = read_component_data(Output, "MOLEFRAC")

            # ---------- 整理 ----------

            all_streams[stream_name] = {

                "stream": stream_name,

                "temperature": temperature,

                "pressure": pressure,

                "vapor_fraction": vapor_fraction,

                "mass_flow": mass_flow,

                "mole_flow": mole_flow,

                "mole_fraction": mole_fraction,

            }

            # ---------- 打印 ----------

            print(
                "Temperature :",
                temperature["value"],
                temperature["unit"],
            )

            print(
                "Pressure    :",
                pressure["value"],
                pressure["unit"],
            )

            print(
                "Vapor Frac  :",
                vapor_fraction["value"],
                vapor_fraction["unit"],
            )

        # ====================================================
        # 6. 获取全部 Blocks
        # ====================================================

        Blocks = Data.Elements("Blocks")

        # Flowsheet 的 Input 节点（MDLTYPE / BLKTYPE 在这里）
        FlowsheetInput = (
            Data
            .Elements("Flowsheet")
            .Elements("Section")
            .Elements("GLOBAL")
            .Elements("Input")
        )

        print("\n========================================")
        print("开始读取 Blocks（含类型识别）")
        print("========================================")

        blocks = []

        connections = []

        block_details = []   # ★ v2 新增：每个设备的类型 + 特有数据

        for block in Blocks.Elements:

            block_name = block.Name

            blocks.append(block_name)

            print("\n----------------------------------------")
            print("当前 Block：", block_name)
            print("----------------------------------------")

            # ================================================
            # ★ v2 新增：设备真实类型 + 类型特有数据
            # ================================================

            detail = get_block_type_data(
                block,
                block_name,
                FlowsheetInput,
            )

            block_details.append(detail)

            print(
                "真实类型   :",
                detail["real_type"],
                "(",
                detail["category"],
                ")",
            )

            print(
                "类型代码   :",
                detail["type_code"],
            )

            print(
                "招牌参数   :",
                len(detail["key_parameters"]),
                "个",
            )

            print(
                "全部参数   :",
                detail["all_parameters_count"],
                "个",
            )

            # 打印招牌参数明细（方便人看）
            for param_path, item in detail["key_parameters"].items():

                print(
                    f"    {param_path:<25}"
                    f"{item['value']} "
                    f"{item['unit']}   "
                    f"{item['description']}",
                )

            # ================================================
            # 获取 Connections（原 v1 逻辑，保持不变）
            # ================================================

            try:

                Connections = block.Elements("Connections")

                inputs = []

                outputs = []

                print("\nConnections：")

                for child in Connections.Elements:

                    stream_name = child.Name

                    try:

                        connection_type = str(child.Value)

                    except Exception:

                        connection_type = ""

                    print("    ", stream_name, "→", connection_type)

                    if "IN" in connection_type:

                        inputs.append(stream_name)

                    elif "OUT" in connection_type:

                        outputs.append(stream_name)

                connections.append({

                    "block": block_name,

                    "inputs": inputs,

                    "outputs": outputs,

                })

            except Exception as e:

                print("Connections 获取失败：", e)

                connections.append({

                    "block": block_name,

                    "inputs": [],

                    "outputs": [],

                    "error": str(e),

                })

        # ====================================================
        # 7. 整理最终结果
        # ====================================================

        result = {

            "success": True,

            "file_path": os.path.abspath(file_path),

            "stream_count": len(all_streams),

            "block_count": len(blocks),

            "connection_count": len(connections),

            "streams": all_streams,

            "blocks": blocks,

            "connections": connections,

            # ★ v2 新增：设备类型明细
            "block_details": block_details,

            # ds: 模拟运行状态 / 报错（供 Agent 查验流程有无报错）
            "simulation_status": read_simulation_status(Data),

        }

        print("\n========================================")
        print("最终 JSON")
        print("========================================")

        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False,
            )
        )

        # ====================================================
        # 8. 输出总结
        # ====================================================

        print("\n========================================")
        print("Aspen Process 数据获取完成（v2）")
        print("========================================")

        print("Block 数量：", len(blocks))

        print("Stream 数量：", len(all_streams))

        print("Connection 数量：", len(connections))

        # ====================================================
        # 9. 返回给 Agent
        # ====================================================

        return result

    # ========================================================
    # 10. 总错误处理
    # ========================================================

    except Exception as e:

        print("\n========================================")
        print("❌ Aspen Process 数据读取失败")
        print("========================================")

        print(e)

        return {

            "success": False,

            "file_path": os.path.abspath(file_path),

            "error": str(e),

        }

    # ========================================================
    # 11. 无论成功还是失败都关闭 Aspen
    # ========================================================

    finally:

        if AspenSimulation is not None:

            try:

                print("\n正在关闭 Aspen Plus...")

                AspenSimulation.Close()

                print("Aspen Plus 已关闭")

            except Exception as e:

                print("Aspen Plus 关闭失败：", e)


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


# ============================================================
# 八、测试入口
# ============================================================

if __name__ == "__main__":

    file_path = (
        "C:\\Users\\Fool\\Desktop\\ChemMateV1工作台"
        "\\10万吨环己烷.bkp"
    )

    result = data_get_process(file_path)

    print("\n========================================")
    print("最终返回结果")
    print("========================================")

    # 不打印全部 JSON（太大），只打印设备类型总览

    if result.get("success"):

        print("\n设备类型总览：")

        for detail in result["block_details"]:

            print(
                f"  {detail['block']:<4}"
                f"{detail['real_type']:<10}"
                f"{detail['category']:<10}"
                f"招牌参数 {len(detail['key_parameters'])} 个 / "
                f"全部参数 {detail['all_parameters_count']} 个",
            )

    else:

        print(result)
