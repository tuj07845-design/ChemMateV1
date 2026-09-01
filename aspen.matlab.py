import win32com.client as win32
import matlab.engine
import os
import time

def run_aspen_matlab_pipeline():
    # 配置路径
    aspen_file_path = r"C:\Users\Fool\Desktop\ChemMateV1\10万吨环己烷.apwz"
    image_save_path = r"C:\Users\Fool\Desktop\ChemMateV1"

    aspen = None
    eng = None

    try:
        # ================= 第一阶段：Python 连接并控制 Aspen Plus =================
        print("[1/4] 正在启动 Aspen Plus COM 服务器...")
        aspen = win32.DispatchEx('Apwn.Document')


        print(f"[2/4] 正在加载模型文件：{aspen_file_path}")
        print(aspen_file_path)
        aspen.InitFromFile2(aspen_file_path)
        aspen.Visible = False

        print("[3/4] 正在运行模拟...")
        run_status = aspen.Run2()
        if run_status != 0:
            print(f"警告：模拟运行状态码为 {run_status}，可能未完全收敛。")

        streams = ['FEED', 'DIST', 'BOTTOM']
        temps = []
        purities = []

        print("[4/4] 正在提取数据...")
        for stream in streams:
            temp_node_path = f"\\Data\\Streams\\{stream}\\Output\\TEMP"
            purity_node_path = f"\\Data\\Streams\\{stream}\\Output\\MOLEFRAC\\MIXED:BENZENE"

            temp_node = aspen.Tree.FindNode(temp_node_path)
            temp_val = temp_node.Value if temp_node else 0.0
            temps.append(float(temp_val))

            purity_node = aspen.Tree.FindNode(purity_node_path)
            purity_val = purity_node.Value if purity_node else 0.0
            purities.append(float(purity_val))

            print(f"  流股 {stream}: 温度={temp_val:.2f}, 纯度={purity_val:.4f}")

        # ================= 第二阶段：Python 调用 MATLAB 进行绘图 =================
        print("[5/6] 正在启动 MATLAB Engine...")
        eng = matlab.engine.start_matlab()

        mat_streams = matlab.cellarray([streams])
        mat_temps = matlab.double([temps])
        mat_purities = matlab.double([purities])
        mat_save_path = image_save_path

        print("[6/6] 调用 MATLAB 绘图函数...")
        eng.plot_aspen_data(
            mat_streams,
            mat_temps,
            mat_purities,
            mat_save_path
        )

        print("流程结束！图片已生成。")

    except Exception as e:
        print(f"发生错误：{e}")

    finally:
        if aspen:
            print("正在关闭 Aspen Plus...")
            aspen.Quit()
            del aspen

        if eng:
            print("正在关闭 MATLAB Engine...")
            eng.quit()
            del eng

if __name__ == "__main__":
    run_aspen_matlab_pipeline()