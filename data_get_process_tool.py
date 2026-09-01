import win32com.client as win32
import os
import json




# ============================================================
# 1. 读取普通数据
# ============================================================

def read_value(output, variable_name):

    """
    读取一个 Aspen 普通数据节点。

    例如：

        TEMP_OUT
        PRES_OUT
        VFRAC_OUT

    返回：

        {
            "value": 数值,
            "unit": 单位
        }
    """

    try:

        node = (
            output
            .Elements(variable_name)
            .Elements("MIXED")
        )


        # --------------------------------------------
        # 读取数值
        # --------------------------------------------

        value = node.Value


        # --------------------------------------------
        # 读取单位
        # --------------------------------------------

        try:

            unit = node.UnitString

        except Exception:

            unit = ""


        return {

            "value": value,

            "unit": unit

        }


    except Exception:

        return {

            "value": None,

            "unit": ""

        }


# ============================================================
# 2. 读取组分数据
# ============================================================

def read_component_data(output, variable_name):

    """
    读取 Aspen 组分数据。

    例如：

        MASSFLOW
        MOLEFLOW
        MOLEFRAC

    返回：

        {
            "组件1": {
                "value": xxx,
                "unit": "kg/hr"
            },

            "组件2": {
                "value": xxx,
                "unit": "kg/hr"
            }
        }
    """

    data = {}


    try:

        node = (
            output
            .Elements(variable_name)
            .Elements("MIXED")
        )


        # --------------------------------------------
        # 遍历所有组分
        # --------------------------------------------

        for component in node.Elements:

            name = component.Name


            # ----------------------------------------
            # 数值
            # ----------------------------------------

            value = component.Value


            # ----------------------------------------
            # 单位
            # ----------------------------------------

            try:

                unit = component.UnitString

            except Exception:

                unit = ""


            # ----------------------------------------
            # 保存
            # ----------------------------------------

            data[name] = {

                "value": value,

                "unit": unit

            }


    except Exception:

        pass


    return data


# ============================================================
# 3. 获取整个 Aspen Process
# ============================================================

def data_get_process(file_path):

    """
    ChemMate V1 - Process Data Tool

    一次读取 Aspen 模型中的：

    1. 全部 Stream 数据
        - temperature
        - pressure
        - vapor_fraction
        - mass_flow
        - mole_flow
        - mole_fraction

    2. 全部 Block

    3. Block 与 Stream 的连接关系

    返回：
        一个完整的 Aspen 流程数据结构
    """


    print("\n========================================")
    print("ChemMate V1 - Data Get Process")
    print("========================================")


    print("\n收到 Aspen 文件路径：")

    print(file_path)


    # ========================================================
    # 4. 检查路径
    # ========================================================

    if not file_path:

        return {

            "success": False,

            "error":
                "没有收到 Aspen 文件路径"

        }


    if not os.path.exists(file_path):

        return {

            "success": False,

            "error":
                "Aspen 文件不存在：" + file_path

        }


    AspenSimulation = None


    try:

        # ====================================================
        # 5. 启动 Aspen
        # ====================================================

        print("\n正在启动 Aspen Plus...")


        AspenSimulation = (
            win32.gencache.EnsureDispatch(
                "Apwn.Document"
            )
        )


        # ====================================================
        # 6. 加载 Aspen 文件
        # ====================================================

        print("正在加载 Aspen 文件...")


        AspenSimulation.InitFromArchive2(
            os.path.abspath(file_path)
        )


        AspenSimulation.Visible = True


        print("Aspen 文件加载成功！")


        # ====================================================
        # 7. 获取 Data
        # ====================================================

        Data = (
            AspenSimulation
            .Tree
            .Elements("Data")
        )


        # ====================================================
        # 8. 获取全部 Streams
        # ====================================================

        STRM = Data.Elements("Streams")


        print("\nStreams 节点获取成功！")


        all_streams = {}


        print("\n========================================")
        print("开始读取全部 Stream")
        print("========================================")


        # ====================================================
        # 9. 遍历 Stream
        # ====================================================

        for Stream in STRM.Elements:

            stream_name = Stream.Name


            print("\n----------------------------------------")

            print(
                "当前 Stream：",
                stream_name
            )

            print("----------------------------------------")


            # =================================================
            # 获取 Output
            # =================================================

            try:

                Output = Stream.Elements(
                    "Output"
                )

            except Exception as e:

                print(
                    "Output 获取失败：",
                    e
                )

                continue


            # =================================================
            # 温度
            # =================================================

            temperature = read_value(
                Output,
                "TEMP_OUT"
            )


            # =================================================
            # 压力
            # =================================================

            pressure = read_value(
                Output,
                "PRES_OUT"
            )


            # =================================================
            # 气相分率
            # =================================================

            vapor_fraction = read_value(
                Output,
                "VFRAC_OUT"
            )


            # =================================================
            # 质量流量
            # =================================================

            mass_flow = read_component_data(
                Output,
                "MASSFLOW"
            )


            # =================================================
            # 摩尔流量
            # =================================================

            mole_flow = read_component_data(
                Output,
                "MOLEFLOW"
            )


            # =================================================
            # 摩尔分率
            # =================================================

            mole_fraction = read_component_data(
                Output,
                "MOLEFRAC"
            )


            # =================================================
            # 整理当前 Stream
            # =================================================

            stream_data = {

                "stream": stream_name,

                "temperature": temperature,

                "pressure": pressure,

                "vapor_fraction": vapor_fraction,

                "mass_flow": mass_flow,

                "mole_flow": mole_flow,

                "mole_fraction": mole_fraction

            }


            # =================================================
            # 保存
            # =================================================

            all_streams[
                stream_name
            ] = stream_data


            # =================================================
            # 打印当前 Stream
            # =================================================

            print(
                "Temperature :",
                temperature["value"],
                temperature["unit"]
            )


            print(
                "Pressure    :",
                pressure["value"],
                pressure["unit"]
            )


            print(
                "Vapor Frac  :",
                vapor_fraction["value"],
                vapor_fraction["unit"]
            )


            print("\nMASS FLOW")


            for component, item in (
                mass_flow.items()
            ):

                print(
                    f"  {component:<15}"
                    f"{item['value']} "
                    f"{item['unit']}"
                )


            print("\nMOLE FLOW")


            for component, item in (
                mole_flow.items()
            ):

                print(
                    f"  {component:<15}"
                    f"{item['value']} "
                    f"{item['unit']}"
                )


            print("\nMOLE FRACTION")


            for component, item in (
                mole_fraction.items()
            ):

                print(
                    f"  {component:<15}"
                    f"{item['value']} "
                    f"{item['unit']}"
                )


        # ====================================================
        # 10. 获取全部 Blocks
        # ====================================================

        Blocks = Data.Elements("Blocks")


        print("\n========================================")

        print("开始读取 Blocks")

        print("========================================")


        blocks = []

        connections = []


        # ====================================================
        # 11. 遍历 Block
        # ====================================================

        for block in Blocks.Elements:

            block_name = block.Name


            blocks.append(
                block_name
            )


            print("\n----------------------------------------")

            print(
                "当前 Block：",
                block_name
            )

            print("----------------------------------------")


            # =================================================
            # 获取 Connections
            # =================================================

            try:

                Connections = (
                    block.Elements(
                        "Connections"
                    )
                )


                inputs = []

                outputs = []


                print("\nConnections：")


                # =================================================
                # 遍历 Connections
                # =================================================

                for child in Connections.Elements:

                    stream_name = child.Name


                    try:

                        connection_type = str(
                            child.Value
                        )

                    except Exception:

                        connection_type = ""


                    print(
                        "    ",
                        stream_name,
                        "→",
                        connection_type
                    )


                    # =================================================
                    # 判断输入
                    # =================================================

                    if "IN" in connection_type:

                        inputs.append(
                            stream_name
                        )


                    # =================================================
                    # 判断输出
                    # =================================================

                    elif "OUT" in connection_type:

                        outputs.append(
                            stream_name
                        )


                # =================================================
                # 保存拓扑
                # =================================================

                connections.append({

                    "block": block_name,

                    "inputs": inputs,

                    "outputs": outputs

                })


            except Exception as e:

                print(
                    "Connections 获取失败：",
                    e
                )


                connections.append({

                    "block": block_name,

                    "inputs": [],

                    "outputs": [],

                    "error": str(e)

                })


        # ====================================================
        # 12. 整理最终结果
        # ====================================================

        result = {

            "success": True,

            "file_path":
                os.path.abspath(
                    file_path
                ),

            "stream_count":
                len(all_streams),

            "block_count":
                len(blocks),

            "connection_count":
                len(connections),

            "streams":
                all_streams,

            "blocks":
                blocks,

            "connections":
                connections

        }

        print("\n========================================")
        print("最终 JSON")
        print("========================================")

        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            )
        )


        # ====================================================
        # 13. 输出总结
        # ====================================================

        print("\n========================================")

        print(
            "Aspen Process 数据获取完成"
        )

        print("========================================")


        print(
            "Block 数量：",
            len(blocks)
        )


        print(
            "Stream 数量：",
            len(all_streams)
        )


        print(
            "Connection 数量：",
            len(connections)
        )


        # ====================================================
        # 14. 返回给 Agent
        # ====================================================

        return result


    # ========================================================
    # 15. 总错误处理
    # ========================================================

    except Exception as e:

        print("\n========================================")

        print(
            "❌ Aspen Process 数据读取失败"
        )

        print("========================================")


        print(e)


        return {

            "success": False,

            "file_path":
                os.path.abspath(
                    file_path
                ),

            "error":
                str(e)

        }


    # ========================================================
    # 16. 无论成功还是失败都关闭 Aspen
    # ========================================================

    finally:

        if AspenSimulation is not None:

            try:

                print(
                    "\n正在关闭 Aspen Plus..."
                )


                AspenSimulation.Close()


                print(
                    "Aspen Plus 已关闭"
                )


            except Exception as e:

                print(
                    "Aspen Plus 关闭失败：",
                    e
                )







if __name__ == "__main__":

    file_path = (
        r"C:\Users\Fool\Desktop\ChemMateV1工作台"
        r"\10万吨环己烷.bkp"
    )


    result = data_get_process(
         file_path
    )


    print("\n========================================")
    print("最终返回结果")
    print("========================================")

    print(result)




















