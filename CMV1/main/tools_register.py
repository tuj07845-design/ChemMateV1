"""ChemMate LangChain 重写版：面向模型的工具层。

原逻辑留在 tools/ 各模块，这里负责：
  1. @tool 注册 + docstring（模型的说明书）
  2. 隐藏模型不该碰的内部参数（process_data / matlab_draw_path / dry_run 等）
  3. 维护"最近一次数据"缓存，供 analyze / draw_mat 自动取数
"""
from langchain.tools import tool

from tools.process_data_get.reader import data_get_process as _data_get_raw
from tools.analyze.analyze_main import analyze_process as _analyze_raw
from tools.draw_mat.draw_mat import draw_mat as _draw_raw
from tools.report_create.report_core import report_create as _report_raw
from tools.bash_tool import bash as _bash_raw

from memory.process_cache import remember_process_data, get_cached_process_data


@tool("data_get_process", parse_docstring=True)
def data_get_process(file_path: str) -> dict:
    """读取 Aspen 文件中的全部股流、设备数据，建立拓扑图。

    返回结果含 simulation_status（status: error/ok/unknown、error_count、errors 列表），
    查验模拟有无报错看它：status=error 说明流程有报错，errors 里是出错设备。
    读取成功后结果自动缓存，analyze_process 和 draw_mat 可直接使用。

    Args:
        file_path: Aspen 文件的绝对路径（.apw/.apwz/.bkp）。
    """
    result = _data_get_raw(file_path)
    if isinstance(result, dict) and result.get("success", True):
        remember_process_data(result)
    return result


@tool("analyze_process", parse_docstring=True)
def analyze_process(component: str | None = None, change_threshold: float = 0.05) -> dict:
    """分析流程数据（数据自动取自最近一次 data_get_process 的结果，无需传数据）。

    返回结构化检查结果 summary/findings、组分追踪表 component_tracking 和前后变化 stream_changes。

    Args:
        component: 组分名，中文名或 Aspen ID 均可，如 "环己烷" 或 "CYCLO-01"。不传则跳过组分追踪。
        change_threshold: 前后变化的判定阈值，默认 0.05（5%）。
    """
    data = get_cached_process_data()
    if data is None:
        return {"success": False, "error": "missing_process_data",
                "message": "还没有流程数据，请先调用 data_get_process。"}
    return _analyze_raw(data, component=component, change_threshold=change_threshold)


@tool("draw_mat", parse_docstring=True)
def draw_mat(
    plot_type: str,
    streams: list[str] | None = None,
    stream: str | None = None,
    component: str | None = None,
    block: str | None = None,
    value_field: str = "mole_fraction",
    title: str = "",
    export: str = "png",
) -> dict:
    """根据最近一次 data_get_process 的结果画图（数据自动取，不要传流程数据）。

    plot_type 四种：
    - stream_tp：流股温度-压力，可选 streams=["S5","S10"] 筛选
    - stream_composition：物流组成，必须带 stream="S5"
    - component_track：组分沿流股分布，必须带 component="CYCLO-01"，value_field 可选 mole_fraction/mole_flow/mass_flow
    - balance_check：设备进出衡算，必须带 block="B7"
    成功时 image_path 是图片路径，可用于 report_create 的 image 块。

    Args:
        plot_type: 图种，上面四种之一。
        streams: 筛选的流股名列表，仅 stream_tp 使用。
        stream: 单条流股名，stream_composition 必填。
        component: 组分名，component_track 必填。
        block: 设备 ID，balance_check 必填。
        value_field: component_track 的纵轴字段，默认 mole_fraction。
        title: 图标题，留空自动生成。
        export: 导出格式，png 或 svg，默认 png。
    """
    return _draw_raw(
        plot_type=plot_type, streams=streams, stream=stream, component=component,
        block=block, value_field=value_field, title=title, export=export,
    )


@tool("report_create", parse_docstring=True)
def report_create(report_type: str, title: str, sections: list[dict]) -> dict:
    """生成 Word("docx") 或 PPT("pptx") 分析报告，成功时 file_path 是报告路径。

    sections 是内容块列表，每块一个 dict，共五种写法：
    - {"type":"heading","level":1,"text":"..."}
    - {"type":"paragraph","text":"..."}
    - {"type":"bullets","items":["..."]}
    - {"type":"table","headers":[...],"rows":[[...]]}
    - {"type":"image","path":"<draw_mat 返回的 image_path>","caption":"图注"}
    报告结论文字由你自己组织，不要照抄工具返回。

    Args:
        report_type: "docx" 或 "pptx"。
        title: 报告标题。
        sections: 内容块列表。
    """
    return _report_raw(report_type=report_type, title=title, sections=sections)


@tool("bash", parse_docstring=True)
def bash(command: str, timeout: int = 60) -> dict:
    """在工作台目录执行一条 shell 命令。仅作兜底：其它工具不够用时（如对 path_finder 找到的文件做简单检查）才允许使用。

    Args:
        command: 简单命令，例如 dir、python xxx.py。禁止删除类危险命令。
        timeout: 超时秒数，默认 60。
    """
    return _bash_raw(command=command, timeout=timeout)