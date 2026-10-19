import os
import shutil
import tempfile
import zipfile
import pythoncom
import win32com.client as win32
from .small_tool import read_value, read_component_data, read_simulation_status
from .block_type import get_block_type_data,get_block_real_type,collect_block_parameters,pick_key_parameters


def _safe_print(*args):
    """诊断输出：stdout 失效（常驻服务控制台/管道被关闭）时静默，不让 print 崩溃主流程。

    常驻 UI 服务里 stdout 句柄可能在两次任务之间失效，此时裸 print 会抛：
        OSError [Errno 22] Invalid argument   —— 句柄被关闭/管道断开
        ValueError I/O operation on closed file —— 流对象已 close()
    二者都会一路上抛成「任务失败」，故统一走本函数。
    """
    try:
        print(*args, flush=True)
    except (OSError, ValueError):
        pass


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
            _safe_print(f"[apwz] 解包方式 {kind} -> {dst}")
            return dst
    except Exception as e:
        _safe_print(f"[apwz] 解包失败: {e}")
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

    _safe_print(f"[data_get] 文件: {file_path}")

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
        _safe_print(f"[data_get] ✓ apwz 已解包 -> {bkp}")
        file_path = bkp

    # COM 初始化：LangGraph 可能在线程池中执行工具，线程未初始化 COM 会报
    # (-2147221008, '尚未调用 CoInitialize。')
    pythoncom.CoInitialize()

    AspenSimulation = None

    try:

        # ====================================================
        # 2. 启动 Aspen
        # ====================================================

        _safe_print("[data_get] 启动 Aspen Plus ...")

        AspenSimulation = (
            win32.gencache.EnsureDispatch(
                "Apwn.Document"
            )
        )

        # ====================================================
        # 3. 加载 Aspen 文件
        # ====================================================

        _safe_print("[data_get] 加载模型 ...")

        AspenSimulation.InitFromArchive2(
            os.path.abspath(file_path)
        )

        AspenSimulation.Visible = True

        _safe_print("[data_get] ✓ 模型已加载")

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

        all_streams = {}

        for Stream in STRM.Elements:

            stream_name = Stream.Name

            # ---------- 获取 Output ----------

            try:

                Output = Stream.Elements("Output")

            except Exception as e:

                _safe_print("Output 获取失败：", e)

                continue

            # ---------- 读取各数据 ----------

            temperature = read_value(Output, "TEMP_OUT")
            pressure = read_value(Output, "PRES_OUT")
            vapor_fraction = read_value(Output, "VFRAC_OUT")

            mass_flow = read_component_data(Output, "MASSFLOW")
            mole_flow = read_component_data(Output, "MOLEFLOW")
            mole_fraction = read_component_data(Output, "MOLEFRAC")
            mass_fraction = read_component_data(Output, "MASSFRAC")


            # ---------- 整理 ----------

            all_streams[stream_name] = {

                "stream": stream_name,

                "temperature": temperature,

                "pressure": pressure,

                "vapor_fraction": vapor_fraction,

                "mass_flow": mass_flow,

                "mole_flow": mole_flow,

                "mole_fraction": mole_fraction,

                "mass_fraction": mass_fraction,

            }

        _safe_print(f"[data_get] ✓ Streams 节点 {len(all_streams)} 条")

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

        blocks = []

        connections = []

        block_details = []   # ★ v2 新增：每个设备的类型 + 特有数据

        for block in Blocks.Elements:

            block_name = block.Name

            blocks.append(block_name)


            # ================================================
            # ★ v2 新增：设备真实类型 + 类型特有数据
            # ================================================

            detail = get_block_type_data(
                block,
                block_name,
                FlowsheetInput,
            )

            block_details.append(detail)


            # ================================================
            # 获取 Connections（原 v1 逻辑，保持不变）
            # ================================================

            try:

                Connections = block.Elements("Connections")

                inputs = []

                outputs = []

                for child in Connections.Elements:

                    stream_name = child.Name

                    try:

                        connection_type = str(child.Value)

                    except Exception:

                        connection_type = ""

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

                _safe_print("Connections 获取失败：", e)

                connections.append({

                    "block": block_name,

                    "inputs": [],

                    "outputs": [],

                    "error": str(e),

                })

        _safe_print(f"[data_get] ✓ Blocks 节点 {len(blocks)} 个")
        _safe_print(f"[data_get] ✓ Connections 节点 {len(connections)} 条")

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

        status = (result.get("simulation_status") or {}).get("status", "unknown")
        _safe_print(
            f"[data_get] 完成  streams={len(all_streams)}  "
            f"blocks={len(blocks)}  connections={len(connections)}  status={status}"
        )

        # ====================================================
        # 9. 返回给 Agent
        # ====================================================

        return result

    # ========================================================
    # 10. 总错误处理
    # ========================================================

    except Exception as e:

        _safe_print(f"[data_get] × 读取失败: {e}")

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

                AspenSimulation.Close()

                _safe_print("[data_get] ✓ Aspen 已关闭")

            except Exception as e:

                _safe_print(f"[data_get] × 关闭失败: {e}")

        pythoncom.CoUninitialize()




