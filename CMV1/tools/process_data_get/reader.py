import os
import json
import shutil
import tempfile
import zipfile
import win32com.client as win32
from .small_tool import read_value, read_component_data, read_simulation_status
from .block_type import get_block_type_data,get_block_real_type,collect_block_parameters,pick_key_parameters


# ============================================================
# 0. apwz 兼容：Aspen OLE 服务不能直接打开 .apwz（归档格式），
#    这里自动把 apwz 里的 .bkp / .bkp.backup 解包出来供 COM 打开。
# ============================================================

def _fix_zip_name(raw):
    """apwz 内条目名多为 GBK 编码，zipfile 按 cp437 读会乱码，这里修正。"""
    try:
        return raw.encode("cp437").decode("gbk")
    except Exception:
        return raw


def _extract_from_apwz(apwz_path):
    """从 .apwz 归档里解出可用的 bkp 文件，返回其路径；失败返回 None。

    优先级：条目中的 .bkp > .bkp.backup（改名 .bkp）> .apw。
    解包缓存目录：<系统临时目录>/chemmate_apwz/
    """
    try:
        with zipfile.ZipFile(apwz_path) as z:
            entries = [(i.filename, i) for i in z.infolist()]
            cache = os.path.join(tempfile.gettempdir(), "chemmate_apwz")
            os.makedirs(cache, exist_ok=True)
            targets = []
            for raw, info in entries:
                n = _fix_zip_name(raw)
                low = n.lower()
                if low.endswith(".bkp") and not low.endswith(".bkp.backup"):
                    targets.append((n, info, "bkp"))
            for raw, info in entries:
                n = _fix_zip_name(raw)
                if n.lower().endswith(".bkp.backup"):
                    targets.append((n[:-7] + ".bkp", info, "backup"))
            for raw, info in entries:
                n = _fix_zip_name(raw)
                if n.lower().endswith(".apw"):
                    targets.append((n, info, "apw"))
            if not targets:
                return None
            n, info, kind = targets[0]
            dst = os.path.join(cache, os.path.basename(n))
            with z.open(info) as src, open(dst, "wb") as out:
                shutil.copyfileobj(src, out)
            print(f"[apwz] 解包方式 {kind} -> {dst}")
            return dst
    except Exception as e:
        print(f"[apwz] 解包失败: {e}")
        return None


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

    requested_path = file_path

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

    # ========================================================
    # 1.5 apwz 兼容：OLE 服务打不开 .apwz，先解包出 .bkp
    # ========================================================

    if str(file_path).lower().endswith(".apwz"):
        bkp = _extract_from_apwz(file_path)
        if bkp is None:
            return {
                "success": False,
                "file_path": file_path,
                "error": "apwz 解包失败：归档内未找到可用的 .bkp / .bkp.backup 文件",
            }
        print(f"已从 apwz 解包，改用: {bkp}")
        file_path = bkp

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

        # apwz 来源时记录原始请求路径（file_path 已是解包后的 bkp）
        if requested_path != file_path:
            result["requested_path"] = requested_path

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




