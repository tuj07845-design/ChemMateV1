# ChemMate V1 · AI 化工流程助手

> 一句自然语言任务，Agent 自主调度 6 个工具：读 Aspen Plus → 诊断流程 → MATLAB 出图 → 生成 Word / PPT 报告。

![License: Non-Commercial](https://img.shields.io/badge/License-Non--Commercial-lightgrey.svg)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.x-1C3C3C?logo=langchain&logoColor=white)

## ✨ 功能特性

- **Agent 全自主闭环**：`create_agent` 推理决策，没有硬编码流程；调哪个工具、传什么参数、何时收尾都由模型判断
- **Aspen Plus 数据引擎**：流股 / 设备 / 拓扑 / 模拟状态一次读完，字段带单位（C、bar、kg/hr…）；兼容 `.bkp` 与 `.apwz`（归档自动解包）
- **确定性诊断层**：衡算校核、报错设备定位、组分追踪、前后变化对比，数值结论由代码算，不靠模型推测
- **MATLAB 专业绘图**：物流温度压力 / 物流组成 / 组分追踪 / 衡算校核 四种图，中文标题与刻度由 MATLAB 渲染
- **中文报告自动生成**：Word / PPT，内嵌 MATLAB 图，排版按宋体 / 黑体规范
- **取数只报状态**：读取 Aspen 时只打印节点完成情况，不再把几千行 JSON 刷到控制台
- **工具调用可视化**：控制台逐条打印 `[n] 工具名(参数)` 与 `✓ 耗时 摘要`，一眼看到 Agent 走到哪一步
- **LangGraph Studio 可观测**：同一个 Agent 挂到 Dev Server，在 Studio 里看完整推理链、逐步回放
- **多模型可切换**：OpenAI 兼容接口，改 `.env` 里一行模型名即可换供应商

## 🏗 架构

```text
用户任务
   │
   ▼
CMV1/main/cmv1_langchain.py        ← 唯一入口：建模型 + 注册工具 + 控制台驱动
   │   模型只看到 6 个工具名和 docstring
   ▼
CMV1/main/tools_register.py        ← 适配层：@tool 装饰 / 缓存读写 / 隐藏内部参数
   │
   ▼
CMV1/tools/…                       ← 实现层：每个模块只对外暴露一个函数
   │
   ▼
Aspen OLE COM · MATLAB · python-docx / python-pptx
```

关键约定：**模型永远看不到 `tools/` 的内部实现**，只看到 `tools_register.py` 里 6 个 `@tool` 的 docstring。
所以实现层怎么重写都行，只要这 6 个签名和返回字典的键名不变。

## 🧰 六个工具

| 工具 | 作用 | 成功返回的关键字段 |
|---|---|---|
| `path_finder` | 在磁盘上定位 `.bkp` / `.apwz` 模型文件 | `file_path` |
| `data_get_process` | 读取 Aspen 全部数据并建立拓扑 | `streams` `blocks` `connections` `simulation_status` |
| `analyze_process` | 诊断 + 组分追踪 + 前后变化（数据自动取缓存） | `summary` `findings` `component_tracking` `stream_changes` |
| `draw_mat` | 四种图，交给 MATLAB 渲染 | `image_path` `caption` `job_dir` |
| `report_create` | 拼装 Word / PPT 报告 | `file_path` `section_count` |
| `bash` | 受限命令执行，仅作兜底 | `stdout` `stderr` `returncode` |

`data_get_process` 成功后结果进 `memory/process_cache.py`，`analyze_process` 与 `draw_mat` 直接复用，不需要重复传数据；也意味着 **同一时刻只服务一个流程**（Aspen 本身也是单实例）。

## 📁 目录结构

```text
ChemMateV1工作台/
├── CMV1/
│   ├── main/
│   │   ├── cmv1_langchain.py          # 入口：模型配置 / 工具列表 / 流式驱动
│   │   └── tools_register.py          # 6 个 @tool：docstring 就是给模型的说明书
│   ├── tools/
│   │   ├── process_data_get/          # Aspen COM 取数（reader / block_type / knowledge_base）
│   │   ├── analyze/                   # 确定性诊断、组分追踪、变化分析
│   │   ├── draw_mat/                  # 拆表 → job → 调 MATLAB（matlab/ 下是 .m 源码）
│   │   ├── report_create/             # Word / PPT 渲染
│   │   ├── component_dicts.py         # 组分中英文别名表
│   │   ├── path_finder_tool.py        # 模型文件定位
│   │   └── bash_tool.py               # 受限命令执行
│   ├── memory/process_cache.py        # 「最近一次 Aspen 数据」进程内缓存
│   ├── LangSmith_GUI/
│   │   └── langgraph_entry.py         # LangGraph Dev Server 入口（无 checkpointer）
│   ├── langgraph.json                 # Dev Server / Studio 配置
│   └── requirements.txt
├── docs/工具层重构/                   # 00-总览 + 五个模块分册
├── model/                             # 示例 Aspen 模型
├── .env.example                       # 环境变量模板
└── README.md
```

## 🚀 快速开始

### 环境要求

- Windows + Python 3.13（Aspen 取数走 COM，需 `pywin32`，仅 Windows 可用）
- Aspen Plus（本机安装并激活）与一份 `.bkp` / `.apwz` 模型文件
- MATLAB（本机验证 R2025b；也可用 `CHEMMATE_MATLAB_BIN` 指定可执行文件）
- 任一 OpenAI 兼容大模型 API

### 安装

```powershell
pip install -r CMV1/requirements.txt
```

`matlabengine` 与 MATLAB 版本严格绑定，没有放进依赖清单，需要时按下面的方式单独装：

```powershell
pip index versions matlabengine
pip install matlabengine==25.2
```

### 配置

在**仓库根目录**创建 `.env`（模板见 `.env.example`）：

```env
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=deepseek-v4.1-flash
```

| 变量 | 必需 | 说明 |
|---|---|---|
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_ID` | 是 | 模型接入三件套 |
| `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` / `LANGSMITH_TRACING` | 否 | 只有用 Studio 看链路时才需要 |
| `CHEMMATE_MATLAB_BIN` | 否 | MATLAB 可执行文件路径，不配则自动探测 |
| `CHEMMATE_MATLAB_MODE` | 否 | `engine` / `batch` / `auto`，默认 `auto` |

`.env` 已在 `.gitignore` 中，不会入库。

### 运行方式一：命令行

```powershell
python CMV1/main/cmv1_langchain.py
```

控制台交互式输入任务，每轮打印工具调用：

```text
任务 > 检查 10万吨环己烷.bkp 全流程有无报错，如有则生成带图的 Word 报告

[1] path_finder(filename=10万吨环己烷.bkp)
    ✓ 28.0s  C:\...\10万吨环己烷.bkp
[2] data_get_process(file_path=C:\...\10万吨环己烷.bkp)
    ✓ 31.8s  流股 12 / 设备 8 / 连接 8 / 模拟 error
[3] analyze_process(component=CYCLO-01)
[4] draw_mat(plot_type=balance_check, block=B8)
    ✓ error 1 / warning 0
    ✓ C:\...\jobs\10万吨环己烷_a6d97476\figure.png
```

输入 `q` 退出。同一进程内多轮对话共享 `thread_id`，上下文连续。

> 上面是实测输出，用的模型是本地测试件 `10万吨环己烷.bkp`；仓库里自带的样例是 `model/Simulation 1.apwz`，换成它的路径即可。

### 运行方式二：LangGraph Studio

在 `CMV1` 目录下启动 Dev Server：

```powershell
cd CMV1
$env:PYTHONUTF8 = "1"      # 中文 Windows 必须：否则 langgraph_api 读内置 JSON 会按 GBK 解码失败
uv run langgraph dev
```

启动成功会打印：

```text
API: http://127.0.0.1:2024
Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
graph_id=chemate
```

Studio 里能看到每个节点的输入输出、每次工具调用与耗时；不联网时用本地的 `http://127.0.0.1:2024/docs` 调接口。

> 入口 `LangSmith_GUI/langgraph_entry.py` 刻意 **不带 checkpointer**：Dev Server 按 thread 自己管持久化，图里自带会被拒绝加载。

## 🔬 一次真实执行

任务：*检查 10 万吨环己烷全流程报错，给出原因与对策并出报告*

```text
path_finder → data_get_process → analyze_process + draw_mat（并行） → report_create
```

实测耗时（DeepSeek 兼容接口 + 本机 Aspen 41.0 / MATLAB R2025b）：

| 阶段 | 耗时 |
|---|---:|
| `path_finder` 定位文件 | ~28s |
| `data_get_process` 读完整流程（12 流股 / 8 设备） | ~32s |
| `analyze_process` 诊断 | ~14s |
| `draw_mat` 出一张图（首次启动 MATLAB 约 49s，后续 12–22s） | 12–49s |
| `report_create` 落盘 docx | ~5s |

最终输出是完整中文结论：定位到 B8 RadFrac 报错、给出进出台账残差（-4.1e-07 kmol/h）、两条可能原因与对应处置。

## 📐 设计要点

- **契约冻结**：6 个工具的函数名、参数名、返回键名是 agent 层与 tools 层之间唯一的接口，改造实现不碰契约
- **结构化返回**：每个工具统一 `success` / `error` / `message`，异常不吞、不伪成功
- **配置零硬编码**：模型、密钥、产物目录全部走环境变量（`CHEMMATE_JOBS_DIR`、`CHEMMATE_REPORTS_DIR`、`CHEMMATE_MATLAB_*`…）
- **产物可追溯**：每次绘图在 `CMV1/jobs/<任务名>_<hash>/` 留一份 `request.json` / `data.csv` / `figure.png`，出问题能复现
- **取数不打屏**：读取过程只输出节点状态，数据本体交给后续工具，控制台保持可读

## 📚 文档

[`docs/工具层重构/`](docs/工具层重构/) 是一套工具层改造手册：

| 文档 | 覆盖范围 |
|---|---|
| [00-总览.md](docs/工具层重构/00-总览.md) | 六条冻结契约、四条改造原则、执行顺序 |
| [01-analyze.md](docs/工具层重构/01-analyze.md) | 诊断层：`findings` 结构、三级组分匹配 |
| [02-draw_mat.md](docs/工具层重构/02-draw_mat.md) | 拆表逻辑、别名匹配、MATLAB 调用链 |
| [03-process_data_get.md](docs/工具层重构/03-process_data_get.md) | COM 调用顺序为什么不能动 |
| [04-report_create.md](docs/工具层重构/04-report_create.md) | 排版细节、sections 校验 |
| [05-独立工具.md](docs/工具层重构/05-独立工具.md) | `bash` 安全边界、`path_finder` 遍历策略 |

## ⚠️ 已知限制

- **Windows only**：Aspen 取数依赖 OLE COM，Linux / macOS 只能跑非取数部分
- **Aspen 单实例**：同一时间只能跑一个任务，并发会争抢 COM 对象
- **首次出图慢**：MATLAB 冷启动要几十秒，之后同进程复用会快很多
- **运行产物不入库**：`CMV1/jobs/`、`CMV1/reports/` 已在 `.gitignore` 中
- **耗时强依赖模型**：深度思考型模型在复杂决策轮可能长达数分钟

## 📜 致谢与许可

- 架构思路受 **Hello-Agents 教程**（[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)）启发；本仓库代码为独立实现，教程版权归原作者所有
- 本项目以 **Non-Commercial License** 发布（见 [LICENSE](LICENSE)）：允许自由查看、学习、研究、个人使用与简历展示；**商业使用需作者书面许可**
- 依赖组件均为 MIT / BSD / PSF 等宽松许可的开源库；Aspen Plus、MATLAB 为商业软件，运行需各自合法授权

---

*ChemMate V1 —— AI × 化工流程工程化 Demo（2026）*
