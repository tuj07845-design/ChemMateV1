# ChemMate V1 Tools 使用指南

> 面向：Agent 开发者与二次开发者。本文件说明 V1 六个工具的职责、参数、返回结构与调用示例。
> 工具实现位于 `CMV1/tools/`，注册表在 `CMV1/agent_main.py` 的 `available_tools`。

## 0. 总览

| 工具 | 作用 | 前置条件 | 典型耗时 |
|---|---|---|---|
| `path_finder` | 按文件名定位 Aspen 模型文件 | 无 | 秒级 |
| `data_get_process` | 读取 Aspen 全部流股/设备/拓扑/模拟状态（兼容 .bkp 与 .apwz） | Aspen Plus 可用 | 30 秒~数分钟（含 Aspen 启动） |
| `analyze_process` | 对取数结果做确定性诊断、组分追踪、变化分析 | 已有 `data_get_process` 结果 | 秒级 |
| `draw_mat` | 生成 MATLAB 专业图表（四种图型） | 已有取数结果 + MATLAB 可用 | ~10 秒 |
| `report_create` | 生成中文 Word / PPT 报告（可内嵌图） | 有内容块（可由模型组织） | 数秒 |
| `bash` | 在工作台目录内执行受限命令 | 无 | 秒级 |

典型链路：`path_finder → data_get_process → analyze_process → draw_mat → report_create`（由 Agent 自主决定顺序）。

---

## 1. `path_finder(filename)`

**作用**：在用户主目录下按文件名搜索 Aspen 模型文件，返回绝对路径。用于用户只给了文件名（如「10万吨环己烷.bkp」）而没给路径的场景。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `filename` | str | ✅ | 文件名（含扩展名），大小写不敏感 |

**返回**：匹配文件的绝对路径（字符串）。找不到时返回提示文本。

**Agent 调用示例**
```text
Action: path_finder(filename="10万吨环己烷.bkp")
```

---

## 2. `data_get_process(file_path)` —— 核心取数工具

**作用**：通过 COM 驱动 Aspen Plus 打开模型，一次性读取全部流股数据、设备信息、连接拓扑与模拟运行状态。

**格式兼容**：`.bkp` 直接打开；`.apwz`（Aspen 归档）会自动解包出内部 `.bkp` 再打开（OLE 服务不支持直接打开 apwz）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file_path` | str | ✅ | Aspen 模型绝对路径（.bkp 或 .apwz） |

**返回关键字段**

| 字段 | 说明 |
|---|---|
| `success` | 成功与否 |
| `file_path` | 实际读取的文件（apwz 时为解包后的 bkp） |
| `requested_path` | 原始请求路径（仅 apwz 场景出现） |
| `stream_count` / `block_count` / `connection_count` | 流股 / 设备 / 连接数量 |
| `streams` | 每条流股：temperature / pressure / vapor_fraction / mass_flow / mole_flow / mole_fraction（**数值带单位**，按组分嵌套） |
| `blocks` / `connections` | 设备列表与进出口拓扑 |
| `block_details` | 每个设备的真实类型、类别、招牌参数（带中文说明）与全参数（v2 新增） |
| `simulation_status` | 模拟运行状态与报错列表（status / error_count / errors） |

**Agent 调用示例**
```text
Action: data_get_process(file_path="C:/Users/Fool/Desktop/ChemMateV1工作台/10万吨环己烷.bkp")
```

**注意**
- Aspen 为单实例：同一时刻只能跑一个取数任务；
- 结果体量很大（完整 JSON 可达数百 KB），V2 计划改为「摘要 + 落盘引用」；
- 失败时返回 `success: false` 与 `error`（如 Aspen 打不开文件、路径不存在）。

---

## 3. `analyze_process(component=None, change_threshold=0.05)`

**作用**：对最近一次取数数据做**确定性**诊断（不做化工理论推理）：基础字段检查、组分追踪、前后变化检测。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `component` | str / None | None | 要追踪的组分（中文名或 Aspen ID，如「环己烷」/「CYCLO-01」） |
| `change_threshold` | float | 0.05 | 判定「明显变化」的阈值 |

**返回关键字段**：`success`、`summary`（流股/设备/连接/错误/警告计数）、`findings`（分级问题列表，level: error/warning/info）、`component_tracking`（组分沿流程分布）、`change_analysis`（前后变化）。

> 数据自动取自最近一次 `data_get_process` 结果（无需重复传数据）。

**Agent 调用示例**
```text
Action: analyze_process(component="CYCLO-01")
```

---

## 4. `draw_mat(plot_type, ...)` —— MATLAB 绘图

**作用**：把取数数据拆成绘图表 → 写 job 目录 → 调 MATLAB 出图 → 回传图片路径。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `plot_type` | str | ✅ | 四种：`stream_tp` / `stream_composition` / `component_track` / `balance_check` |
| `streams` | list | None | 仅 `stream_tp`：筛选流股，如 `["S5","S10"]` |
| `stream` | str | None | 仅 `stream_composition`：指定流股，如 `"S5"` |
| `component` | str | None | 仅 `component_track`：指定组分 |
| `block` | str | None | 仅 `balance_check`：指定设备，如 `"B7"` |
| `value_field` | str | `mole_fraction` | `component_track` 取值字段：mole_fraction / mole_flow / mass_flow |
| `title` | str | "" | 自定义图标题（默认自动生成） |
| `export` | str | `png` | 导出格式：png / svg |

**返回关键字段**：`success`、`image_path`（图片绝对路径）、`caption`、`job_dir`（本次绘图任务目录，目录名含模型名便于追溯）、`warnings`。失败时 `error` 为 `matlab_failed` / `missing_process_data` / `spec_invalid` / `data_not_found` 等。

**Agent 调用示例**
```text
Action: draw_mat(plot_type="balance_check", block="B8")
Action: draw_mat(plot_type="stream_tp", streams=["S5","S10"])
```

**环境变量**：`CHEMMATE_MATLAB_BIN`（MATLAB 可执行文件）、`CHEMMATE_MATLAB_DRAW`（MATLAB 脚本目录）、`CHEMMATE_JOBS_DIR`（job 目录根）。

---

## 5. `report_create(report_type, title, sections)`

**作用**：把结构化内容块渲染成中文 Word / PPT 报告（宋体正文、黑体标题、跨页表格规则），可内嵌 `draw_mat` 产出的图片。

| 参数 | 类型 | 说明 |
|---|---|---|
| `report_type` | str | `docx` 或 `pptx` |
| `title` | str | 报告标题 |
| `sections` | list[dict] | 内容块列表，见下表 |

**内容块类型**

| type | 字段 | 说明 |
|---|---|---|
| `heading` | `level`, `text` | 标题 |
| `paragraph` | `text` | 段落 |
| `bullets` | `items` | 项目符号列表 |
| `table` | `headers`, `rows` | 表格 |
| `image` | `path`, `caption` | 图片（path 用 draw_mat 返回的 image_path） |

**返回关键字段**：`success`、`file_path`（报告绝对路径）。报告默认输出到 `CHEMMATE_REPORTS_DIR` 或 `cwd/reports`。

**Agent 调用示例**
```text
Action: report_create(report_type="docx", title="环己烷流程报错检查报告", sections=[{"type":"heading","level":1,"text":"一、模拟概述"},{"type":"paragraph","text":"..."},{"type":"image","path":"...figure.png","caption":"图1 设备衡算"}])
```

---

## 6. `bash(command, timeout=60)`

**作用**：在工作台目录内执行受限 shell 命令（如 `dir`、`python xxx.py`）。**仅用于辅助场景**（如定位文件、查看目录），不得用于模型参数修改。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `command` | str | ✅ | 要执行的命令 |
| `timeout` | int | 60 | 超时秒数 |

**返回**：`success`、`stdout`、`stderr`、`returncode`。

**安全限制**：工作目录锁定在工作台内；黑名单拦截 `rm -rf`、`format`、`shutdown`、`reg delete` 等危险命令。

---

## 7. 给二次开发者的提示

1. **加一个新工具**：在 `CMV1/tools/` 下建包 → 实现函数（返回结构化 dict，含 `success`）→ 在包的 `__init__.py` 导出 → 在 `agent_main.py` 的 `available_tools` 注册 → 在 `agents/system_prompt.py` 补充工具说明（模型才知道怎么调）。
2. **工具约定**：单一职责、参数显式、返回统一 `success/error/message`、失败绝不伪成功、可独立测试。
3. **数据流**：`data_get_process` 结果由主程序缓存（memory/process_cache）并在调用 `analyze_process` / `draw_mat` 时自动注入，避免大 JSON 反复传参。
4. **排查工具问题**：先单独跑该工具函数（绕过 Agent），确认是工具问题还是 Agent 调用参数问题。

---

*配套文档：`docs/V1工程化验收报告.md`（工具工程化评分与证据）、`docs/ChemMateV1重构操作说明书.md`（拆分与接入细节）。*