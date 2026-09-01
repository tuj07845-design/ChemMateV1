# ChemMate V1 重构操作说明书

> 对象：代码小白（你本人）
> 原则：**所有代码改动都由你亲手完成**，本说明书只负责把每一步讲清楚。
> 配套阅读：`ChemMate V1 现状盘点与下一步行动计划.docx`（总体规划）、`cmv1心得.docx`（开发方法论）、`ChemMate V1历程.docx`（17 天踩坑记录）

## 目录

- 第 0 节　开工前必读（3 件事）
- 第 1 节　现状评审结论（我已帮你做完）
- 第 2 节　Git 基线快照（我已帮你做完 + 使用说明）
- 第 3 节　目标：重构后的目录长什么样
- 第 4 节　第一步：大工具拆分（最费时，先做）
- 第 5 节　第二步：目录重组（tools / agents / memory + 新主程序）
- 第 6 节　第三步：.env 环境变量覆盖 API 密钥
- 第 7 节　Python 语法速查（代码小白专用，看不懂代码时回来查）
- 第 8 节　全流程验证清单（做完打勾）
- 第 9 节　Git 常用命令速查（新手版）

---

## 0. 开工前必读（3 件事）

### 0.1 你现在的工作台是什么

一句话概括：**Python 是总调度，Aspen Plus 提供数据，MATLAB 画图，最后自动生成 Word/PPT 报告，中间有一个"大模型 Agent"负责指挥每一步**。所有核心代码都在 `CMV1/` 文件夹里，根目录还有几个早期旧脚本。

### 0.2 你要亲手做的三件事（就是你说的三点）

1. **拆分大文件**：`analyzer_tool.py`（1814 行）、`data_get_process_tool_v2.py`（1371 行）、`report_tool.py`（837 行）太大，拆成多个小文件。
2. **目录重组**：所有工具放一个文件夹（`tools/`），Agent 相关放一个文件夹（`agents/`），记忆/缓存放一个文件夹（`memory/`），新主程序 `agent_main.py` 统一调用。
3. **密钥搬家**：把写死在代码里的 API 密钥改到 `.env` 文件，用环境变量读取（覆盖）。

### 0.3 你不需要害怕的三件事

- **拆文件拆不坏**：Git 基线快照已经做好（第 2 节），任何时候改坏都能一键还原。
- **Python 语法不难**：第 7 节是专门为你写的速查，遇到不懂的回来查。
- **每步都有验证方法**：做完一步跑一条验证命令，错了马上知道，不会"憋到最后才发现"。

---

## 1. 现状评审结论（我已帮你做完）

### 1.1 资产清单

| 类别 | 位置 | 说明 | 规模 |
|---|---|---|---|
| Aspen 模型 | 根目录 `10万吨环己烷.apwz / .bkp` | V1 全部工具的验证载体 | 73KB / 311KB |
| Agent 主控 | `CMV1/CMV测试agent.py` | 大模型调用 + 自研 Action 文本协议解析工具调用 | 505 行 |
| 取数工具 | `CMV1/data_get_process_tool_v2.py` | 读取股流/拓扑/设备特有数据，V1 核心（v2 增强版） | 1371 行 |
| 诊断工具 | `CMV1/analyzer_tool.py` | 对模拟结果做确定性检查、组分追踪、前后变化分析 | 1814 行 |
| 绘图链路 | `CMV1/draw_mat.py` + `tables.py` + `jobs.py` + `matlab_backend.py` + `matlab/draw/*.m` | Python 拆数、写 job 目录，MATLAB 出图 | — |
| 报告工具 | `CMV1/report_tool.py` | 生成 Word/PPT 中文排版报告 | 837 行 |
| 小工具 | `path_finder_tool.py`、`bash_tool.py`、`process_store.py` | 文件定位、命令执行、进程内数据缓存 | 各几十行 |
| Web 演示 | `CMV1/ui/`（server.py + agent/ + tools/ + frontend/） | Mock 模式的网页控制台，未接真实工具 | — |
| 经验文档 | 根目录 3 个 .docx | 历程、心得、行动计划 | — |
| 旧脚本 | 根目录 `data_get_process_tool.py`、`path_finder.py`、`aspen.matlab.py`、`aspen_tree_finder指导.py` | 早期版本，已被 CMV1/ 内新版本取代 | — |

### 1.2 发现的问题（按严重程度排序）

**问题 1（最严重）：API 密钥明文写死在代码里**
`CMV1/CMV测试agent.py` 第 348–353 行有 LLM 密钥（`sk-` 开头）和 Tavily 搜索密钥（`tvly-` 开头）。任何一次截图、上传、分享代码都会泄露，存在被盗刷风险。→ 第 6 节解决。

**问题 2：没有版本控制（已解决）**
整个工作台之前没有 git 仓库，17 天迭代没有任何快照。→ 第 2 节已建好基线。

**问题 3：大文件（三个 800+ 行的工具文件）**
`analyzer_tool.py` 1814 行、`data_get_process_tool_v2.py` 1371 行、`report_tool.py` 837 行。一次打开、查找、修改都很困难。→ 第 4 节解决。

**问题 4：结构混乱**
- 工具文件平铺在 `CMV1/` 根目录，没有分类。
- 新旧脚本并存：根目录还有旧版 `data_get_process_tool.py`、`path_finder.py`，容易误引用。
- `__pycache__`、`.idea` 等中间产物混在目录里。→ 第 5 节 + .gitignore 解决。

**问题 5：没有依赖清单**
缺少 `requirements.txt`，换电脑或重装环境时不知道要装哪些包。→ 第 5.7 节解决。

### 1.3 主链关系图（谁调用谁）

~~~text
                    ┌─────────────────────────────┐
                    │   CMV测试agent.py（主程序）   │
                    │   ① 调用大模型 ② 解析 Action  │
                    │   ③ 调用工具 ④ 循环直到 Finish │
                    └──────┬──────────┬───────────┘
          import（第 30–34 行）         │
        ┌───────────────┬───┴────┬──────────────┐
        ▼               ▼        ▼              ▼
 data_get_process  path_finder analyze_process  draw_mat  report_create
 (v2 取数)          (找文件)     (诊断)          (绘图)      (Word/PPT)
        │                                   │
        ▼                                   ▼
 Aspen Plus (COM)              tables.py 拆数 → jobs.py 写任务
        │                     → matlab_backend.py → MATLAB 出图
        ▼
 结果存进 _last_data_get_result（进程内缓存，供 analyze/draw 复用）
~~~

> 你的任务就是把这个"平铺的一家人"整理成"分房间住"（第 3 节的目标结构），并给密钥换个安全的家（第 6 节）。

---

## 2. Git 基线快照（我已帮你做完）

### 2.1 我做了什么

1. 用 `git init` 初始化了仓库（分支名 `main`）；
2. 写了 `.gitignore`（把 `__pycache__/`、`.idea/`、`.env` 等排除在版本控制外）；
3. 提交了第一个快照：**commit `76895e8`**，83 个文件、12009 行代码。

现在整个工作台处于"干净"状态（没有未提交的改动），这就是你的"后悔药"。

### 2.2 验证快照存在

在 PyCharm 底部 **Terminal**（终端）里输入：

~~~bash
git log --oneline
~~~

应该看到一行：

~~~text
76895e8 ChemMate V1 基线快照：取数到诊断到绘图到报告全链路 17 天成果
~~~

> 注意：如果提示 `git 不是内部或外部命令`，说明你的终端没找到 git。用完整路径即可：
> `& "C:/Program Files/Git/cmd/git.exe" log --oneline`
> 推荐在 PyCharm → Settings → Version Control → Git 里把 Path to Git executable 填成 `C:/Program Files/Git/cmd/git.exe`，以后就能直接敲 `git` 了。

### 2.3 改坏了的急救方法（背下来）

| 情况 | 命令 |
|---|---|
| 只放弃某个文件的改动 | `git checkout -- 文件名` |
| 放弃所有未提交的改动，回到最后一次提交 | `git checkout -- .` |
| 看看现在改了什么 | `git status` |
| 看看某个文件具体改了哪些行 | `git diff 文件名` |
| 把改动暂存（准备提交） | `git add .` |
| 提交一个快照 | `git commit -m "这次改了什么"` |

### 2.4 重要习惯

**每完成一节就提交一次**。例如拆完 analyzer_tool 后：

~~~bash
git add .
git commit -m "拆分 analyzer_tool 完成"
~~~

这样每一步都可回退，永远不怕改坏。

---

## 3. 目标：重构后的目录长什么样

最终目标（重构完成后）：

~~~text
ChemMateV1工作台/                          ← 项目根目录
├── .git/                                 ← git 历史（已建好，别删）
├── .gitignore                            ← git 忽略规则（已建好）
├── .env                                  ← 密钥文件（第 6 节自己建！绝不能被提交）
├── .env.example                          ← 密钥模板（可以提交，给别人看格式）
├── ChemMateV1重构操作说明书.md             ← 就是本文件
├── 10万吨环己烷.apwz / .bkp               ← Aspen 模型（不动）
├── ChemMate V1 现状盘点与下一步行动计划.docx（不动）
├── ChemMate V1历程.docx / cmv1心得.docx   ←（不动）
├── legacy/                               ← 旧脚本归档（第 5.2 节新建）
└── CMV1/                                 ← 主角在这里
    ├── agent_main.py                     ← 新主程序（由 CMV测试agent.py 改造）
    ├── config.py                         ← 配置中心（读 .env）
    ├── requirements.txt                  ← 依赖清单
    ├── tools/                            ← 【所有工具】
    │   ├── __init__.py
    │   ├── data_get/                     ← 取数（由 data_get_process_tool_v2.py 拆分）
    │   │   └── __init__.py               ← 对外只暴露 data_get_process
    │   ├── analyze/                      ← 诊断（由 analyzer_tool.py 拆分）
    │   │   └── __init__.py               ← 对外只暴露 analyze_process
    │   ├── draw/                         ← 绘图（draw_mat + tables + jobs + matlab_backend）
    │   │   └── __init__.py               ← 对外只暴露 draw_mat
    │   ├── report/                       ← 报告（由 report_tool.py 拆分）
    │   │   └── __init__.py               ← 对外只暴露 report_create
    │   ├── path_finder.py                ← 文件定位（原 path_finder_tool.py）
    │   └── bash_tool.py                  ← 命令执行
    ├── agents/                           ← 【Agent 层】
    │   ├── __init__.py
    │   ├── llm_client.py                 ← 大模型客户端（原 OpenAICompatibleClient 类）
    │   ├── action_parser.py              ← Action 文本协议解析（原 4 个解析函数）
    │   └── system_prompt.py              ← 系统提示词（原 AGENT_SYSTEM_PROMPT）
    ├── memory/                           ← 【记忆层】
    │   ├── __init__.py
    │   └── process_cache.py              ← "最近一次取数结果"缓存（原 draw_mat 里的缓存）
    ├── ui/                               ← Web 演示界面（保持不动）
    ├── matlab/                           ← MATLAB 绘图脚本（保持不动）
    └── reports/                          ← 生成的报告（保持不动）
~~~

**三个核心思想（记牢）：**

1. **tools/ 只管"干活"**：每个工具文件夹的 `__init__.py` 对外只暴露 1–2 个函数，主程序和其他工具永远通过 `from tools.xxx import yyy` 调用，内部怎么拆都不影响外面。
2. **agents/ 只管"指挥"**：调大模型、解析模型的回复、组织循环。它不认识 Aspen，也不画图。
3. **memory/ 只管"记东西"**：跨工具共享的数据（比如"最近一次取数结果"）放这里，避免工具之间传大 JSON。

---

## 4. 第一步：大工具拆分（最费时，先做）

### 4.1 通用拆分方法（8 步法）—— 先读这个！

拆文件不神秘，本质就是"**把一个大文件里的函数，按功能搬进不同的小文件，再让入口能重新找到它们**"。每一步如下：

1. 在 PyCharm 里打开要拆的文件，先通读文件头部的注释（每个文件开头都写了"本文件作用"）。
2. 按 `Ctrl+F` 搜 `def `，把所有函数名和行号记下来（**下表已帮你标好行号**，照着搬即可）。
3. 新建目标文件夹：在 PyCharm 里右键 → New → Python Package，输入名字（如 `analyze`）。**PyCharm 会自动生成 `__init__.py`**，这个文件是"包的身份证"，没有它 Python 就不认这个文件夹是包。
4. 打开原文件，把某个函数**整段剪切**：从 `def 函数名(...):` 那一行开始，到它缩进结束（return 之后空行）为止。PyCharm 左侧有个折叠小三角 ▸，点一下可以看到函数边界，帮助确认没多剪没少剪。
5. 粘贴到新文件里。新文件顶部要补上这个函数用到的 `import`——看看原文件顶部有哪些 import，这个函数用到了哪个就复制哪个过来。
6. 函数之间互相调用的，改成**相对导入**：同包内用 `from .模块名 import 函数名`（点号表示"当前包"）。例如 `analyze/analyze_main.py` 里要调用 `basic_checks.py` 的 `check_process`，就写 `from .basic_checks import check_process`。
7. 跑一次验证（第 4.6 节），确认结果和原来一样。
8. `git add . && git commit -m "拆分 xxx 完成"`。

**三个易错点（划重点）：**
- 一个函数是一个整体，**永远不要拆半个函数**。
- 顶部 import 别乱删。拆完跑一遍，报 `ModuleNotFoundError` 就是缺 import，报 `NameError` 就是某个函数/变量没导入。
- 大文件顶部经常有一段**常量定义**（如知识库字典、字体常量），它们被很多函数共用，建议放进对应包的 `_constants.py` 或留在入口文件。

---

### 4.2 analyzer_tool.py（1814 行）→ `tools/analyze/`

这个文件内部其实已经有编号分段注释（①基础数据检查 ②流程检查 ③查找组件 ④比较 Stream ⑤前后变化 ⑥主分析 ⑦入口），非常好拆。**拆成 5 个新文件**：

| 新文件 | 放进去的函数（括号内是原文件行号） | 职责 |
|---|---|---|
| `analyze/utils.py` | `_number`(28) `_value`(62) `_unit`(80) `_numeric_value`(98) `_find_key`(133) `_stream_summary`(187) | 公共小工具（被所有文件用到） |
| `analyze/basic_checks.py` | `check_stream`(247) `check_process`(525) | ①②基础数据检查、流程检查 |
| `analyze/component_track.py` | `find_component`(841) | ③查找组分 |
| `analyze/change_analysis.py` | `compare_streams`(1080) `detect_stream_changes`(1327) | ④⑤比较与变化分析 |
| `analyze/analyze_main.py` | `_coerce_process_data`(1460) `analyze`(1528) `analyze_process`(1758) | ⑥⑦主分析函数 + 对外入口 |
| `analyze/__init__.py` | 只写一行导出（见下） | 包入口 |

`analyze/__init__.py` 的内容（照抄）：

~~~python
# -*- coding: utf-8 -*-
"""诊断工具包：对外只暴露 analyze_process 和 analyze。"""
from .analyze_main import analyze, analyze_process
~~~

**注意：** `analyze_main.py` 用到 `check_process`、`find_component`、`compare_streams`、`detect_stream_changes` 和 utils 里的函数，所以它顶部的 import 要写成：

~~~python
from .utils import _number, _value, _unit, _numeric_value, _find_key, _stream_summary
from .basic_checks import check_process
from .component_track import find_component
from .change_analysis import compare_streams, detect_stream_changes
~~~

> 拆完原文件怎么办？可以删除，也可以先留着备份（建议先留到确认没问题再删，或放进 `legacy/`）。

---

### 4.3 data_get_process_tool_v2.py（1371 行）→ `tools/data_get/`

这个文件是"取数工具 v2"（你说要拆的 process v2）。内部结构：①类型知识库（一段大字典）→ 4 个设备类型函数 → 大函数 `data_get_process` → 3 个小工具函数。**拆成 5 个新文件**：

| 新文件 | 放进去的内容（原行号） | 职责 |
|---|---|---|
| `data_get/knowledge_base.py` | 类型知识库字典（第 55–249 行，即"一、类型知识库"整段） | 设备类型 → 中文名/招牌参数 的对照表 |
| `data_get/block_type.py` | `get_block_real_type`(253) `collect_block_parameters`(319) `pick_key_parameters`(460) `get_block_type_data`(581) | 读设备类型和特有参数 |
| `data_get/reader.py` | `data_get_process`(675) | 主函数：启动 Aspen、读全部数据（先原样搬，第二阶段再细化） |
| `data_get/small_helpers.py` | `read_value`(1102) `read_component_data`(1149) `read_simulation_status`(1205) | 小工具函数 |
| `data_get/__init__.py` | 一行导出 | 包入口 |

`data_get/__init__.py` 内容：

~~~python
# -*- coding: utf-8 -*-
"""取数工具包：对外只暴露 data_get_process。"""
from .reader import data_get_process
~~~

**关于 427 行的大函数 `data_get_process`（第二阶段再做，不急）：**
它内部有编号注释步骤（1.检查路径 → 2.启动 Aspen → 3.读股流 → 4.读设备 → ...），以后可以逐步把每个"步骤块"提成小函数。**第一次拆分别动它**，先原样搬过去保证能跑，熟悉了再细化。

---

### 4.4 report_tool.py（837 行）→ `tools/report/`

这个文件分两大块：Word 渲染、PPT 渲染，外加主函数和"把结果拼成报告内容"的函数。**拆成 4 个新文件**：

| 新文件 | 放进去的函数（原行号） | 职责 |
|---|---|---|
| `report/render_docx.py` | `_docx_style_font`(178) `_docx_run_font`(186) `_docx_first_line_indent`(201) `_docx_add_page_number`(210) `_render_docx`(233) | Word 排版渲染 |
| `report/render_pptx.py` | `_pptx_run_font`(380) `_render_pptx`(403) `new_slide`(440) `reset_body`(461) `ensure_space`(469) | PPT 排版渲染 |
| `report/report_core.py` | `ReportError`(109) `_check_lib`(122) `_validate_sections`(146) `_default_output_path`(606) `report_create`(620) `_fail`(674) | 主函数 + 校验 + 错误处理 |
| `report/sections.py` | `build_sections_from_results`(689) `_fmt`(797) `_fmt_unit`(806) `tool_spec`(817) | 把工具结果拼成报告内容块 |
| `report/__init__.py` | 一行导出 | 包入口 |

`report/__init__.py` 内容：

~~~python
# -*- coding: utf-8 -*-
"""报告工具包：对外只暴露 report_create 和 build_sections_from_results。"""
from .report_core import report_create
from .sections import build_sections_from_results
~~~

> 注意：`report_core.py` 里的 `report_create` 会调用 `_render_docx` / `_render_pptx`，所以 report_core.py 顶部要写：
> `from .render_docx import _render_docx` 和 `from .render_pptx import _render_pptx`。

---

### 4.5 绘图链路归位（不拆分，只搬家）

`draw_mat.py`（274 行）、`tables.py`（315 行）、`jobs.py`（109 行）、`matlab_backend.py`（181 行）、`process_store.py`（19 行）这几个文件互相配合，整体搬进 `tools/draw/`：

| 新文件 | 来源 | 说明 |
|---|---|---|
| `tools/draw/draw_mat.py` | `CMV1/draw_mat.py` | 主绘图函数 |
| `tools/draw/tables.py` | `CMV1/tables.py` | 拆数 |
| `tools/draw/jobs.py` | `CMV1/jobs.py` | 任务目录读写 |
| `tools/draw/matlab_backend.py` | `CMV1/matlab_backend.py` | MATLAB 引擎 |
| `tools/draw/process_store.py` | `CMV1/process_store.py` | 进程内缓存（也可并入 memory/，见 5.4） |
| `tools/draw/__init__.py` | 新建 | 导出 `draw_mat` |

`tools/draw/__init__.py` 内容：

~~~python
# -*- coding: utf-8 -*-
"""绘图工具包：对外只暴露 draw_mat。"""
from .draw_mat import draw_mat
~~~

**搬家后必须同步改的 import（这是最容易被坑的地方）：**
- `draw_mat.py` 内部原来写 `import tables`、`import jobs`、`from matlab_backend import ...`，要改成 `from .tables import ...`、`from .jobs import ...`、`from .matlab_backend import ...`（点号 = 同一包内）。
- `matlab_backend.py` 里如果引用了 MATLAB 脚本路径（`matlab/draw/*.m`），用的是相对路径，搬家后注意路径层级没变（`CMV1/tools/draw/` 和 `CMV1/matlab/` 之间隔了一层，若代码里用 `Path(__file__)` 定位就没问题，若是写死相对路径就要 +1 层 `../..`）。

---

### 4.6 怎么验证"拆完没拆坏"

拆完一个包后，在 `CMV1` 目录下运行（注意：**必须在 CMV1 目录下运行**，因为包都在 CMV1 下面）：

~~~bash
python -c "from tools.analyze import analyze_process; print('analyze 导入 OK')"
python -c "from tools.data_get import data_get_process; print('data_get 导入 OK')"
python -c "from tools.report import report_create; print('report 导入 OK')"
python -c "from tools.draw import draw_mat; print('draw 导入 OK')"
~~~

能打印 OK 就说明这个包的 import 链路通了。**更强的验证**是跑真实功能：

~~~bash
cd CMV1
python test_draw_mat.py          # 原绘图测试，验证 draw 链路
python -c "from tools.data_get import data_get_process; r = data_get_process('C:/Users/Fool/Desktop/ChemMateV1工作台/10万吨环己烷.bkp'); print(r.get('success'))"
~~~

（第二条会真的启动 Aspen，比较慢，第一次跑需要几分钟，请耐心。）

---

## 5. 第二步：目录重组（tools / agents / memory + 新主程序）

### 5.1 建目录

在 PyCharm 里对 `CMV1` 右键 → New → Python Package，依次创建：

`tools`、`tools/data_get`、`tools/analyze`、`tools/draw`、`tools/report`、`agents`、`memory`，再对根目录右键 → New → Directory 创建 `legacy`（归档用，不需要 __init__.py）。

> 小知识：`__init__.py` 就是"包的身份证"。文件夹里有它，Python 才认这是"包"，才能用 `from 文件夹 import 东西`。空文件也可以，里面写说明和导出更好。

### 5.2 移动小工具（用 git mv，保留历史）

在 `CMV1` 目录下（PyCharm Terminal）：

~~~bash
git mv CMV1/path_finder_tool.py  CMV1/tools/path_finder.py
git mv CMV1/bash_tool.py         CMV1/tools/bash_tool.py
git mv CMV1/tables.py            CMV1/tools/draw/tables.py
git mv CMV1/jobs.py              CMV1/tools/draw/jobs.py
git mv CMV1/matlab_backend.py    CMV1/tools/draw/matlab_backend.py
git mv CMV1/draw_mat.py          CMV1/tools/draw/draw_mat.py
git mv CMV1/process_store.py     CMV1/tools/draw/process_store.py
git mv CMV1/report_tool.py       CMV1/tools/report/report_tool.py   # 先整体搬，再按 4.4 拆
git mv CMV1/analyzer_tool.py     CMV1/tools/analyze/analyzer_tool.py # 先整体搬，再按 4.2 拆
git mv CMV1/data_get_process_tool_v2.py  CMV1/tools/data_get/data_get_process_tool_v2.py # 先整体搬，再按 4.3 拆
~~~

> `git mv` = 移动 + 告诉 git"这是搬家不是删除重写"，这样以后看历史还能看到文件原来的样子。
> 先搬、后拆的好处：任何时候跑 4.6 的验证都能通过，风险最小。

根目录旧脚本归档（同样在根目录 Terminal）：

~~~bash
git mv data_get_process_tool.py  legacy/
git mv path_finder.py            legacy/
git mv aspen.matlab.py           legacy/
git mv aspen_tree_finder指导.py   legacy/
~~~

> 归档 ≠ 删除。先搬走，等确认新代码完全不依赖它们，再删也不迟（用 `git rm`）。

### 5.3 把主程序拆出 agents/（从 CMV测试agent.py 里切）

打开 `CMV1/CMV测试agent.py`，按行号切出三块：

| 新文件 | 剪切的内容（原行号） | 说明 |
|---|---|---|
| `agents/system_prompt.py` | 第 1–28 行（`AGENT_SYSTEM_PROMPT = """..."""` 整段） | 系统提示词 |
| `agents/llm_client.py` | 第 41–69 行（`from openai import OpenAI` + `class OpenAICompatibleClient`） | 大模型客户端 |
| `agents/action_parser.py` | 第 72–344 行（`import re, ast, os, json` + `_extract_finish_answer`、`_split_top_level`、`_parse_value`、`_parse_tool_call`、`_observation_text`） | Action 文本解析 |

`agents/llm_client.py` 顶部内容（照抄即可）：

~~~python
# -*- coding: utf-8 -*-
"""大模型客户端：兼容 OpenAI 接口的 LLM 调用。"""
from openai import OpenAI


class OpenAICompatibleClient:
    """一个用于调用任何兼容 OpenAI 接口的 LLM 服务的客户端。"""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, system_prompt: str) -> str:
        """调用 LLM API 来生成回应。"""
        print("正在调用大语言模型...")
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
            )
            answer = response.choices[0].message.content
            print("大语言模型响应成功。")
            return answer
        except Exception as e:
            print(f"调用LLM API时发生错误: {e}")
            return "错误:调用语言模型服务时出错。"
~~~

`agents/action_parser.py` 里 5 个函数互相调用，搬的时候注意：`_parse_tool_call` 用到 `_split_top_level` 和 `_parse_value`，`_observation_text` 独立。因为都在同一个文件里，**互相调用不用改**，原样搬即可。

### 5.4 memory/ 放什么（记忆层）

`memory/process_cache.py` —— 把 draw_mat.py 里的"最近一次取数结果"缓存逻辑搬过来，再吸收 process_store.py 的职责：

~~~python
# -*- coding: utf-8 -*-
"""记忆层：进程内的"最近一次取数结果"缓存。

analyze_process / draw_mat 不显式传 process_data 时，
主程序从这里取数据自动注入，避免大 JSON 反复传参。
"""
_LAST_PROCESS_DATA = None


def remember_process_data(data):
    """保存最近一次 data_get_process 的完整结果，返回原值。"""
    global _LAST_PROCESS_DATA
    _LAST_PROCESS_DATA = data
    return data


def get_cached_process_data():
    """取回最近一次结果；没有则返回 None。"""
    return _LAST_PROCESS_DATA
~~~

然后 `tools/draw/draw_mat.py` 里原本的 `remember_process_data` / `get_cached_process_data` 改成从 memory 导入：

~~~python
from memory.process_cache import remember_process_data, get_cached_process_data
~~~

（可选）`memory/session_log.py`：把每次工具调用的参数、结果摘要、耗时写成 JSONL 日志，方便排查问题。这是第二期工程化内容，现在不做也行。

### 5.5 新主程序 agent_main.py（完整代码）

把 `CMV测试agent.py` **复制**为 `agent_main.py`（`git mv CMV测试agent.py CMV1/agent_main.py` 也行，建议保留旧文件作对照，用复制），然后按下面改：

**① 顶部 import 区**（第 30–41 行附近）改成：

~~~python
import os
import re
import ast
import json

from dotenv import load_dotenv
load_dotenv()  # ★ 第 1 件事：读取 .env（必须先于一切配置）

# ---- 工具层 ----
from tools.data_get import data_get_process
from tools.path_finder import path_finder
from tools.analyze import analyze_process
from tools.draw import draw_mat
from tools.report import report_create, build_sections_from_results

# ---- Agent 层 ----
from agents.llm_client import OpenAICompatibleClient
from agents.action_parser import (
    _extract_finish_answer,
    _parse_tool_call,
    _observation_text,
)
from agents.system_prompt import AGENT_SYSTEM_PROMPT

# ---- 配置 ----
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_ID, TAVILY_API_KEY

# 工具注册表（和原来一模一样）
available_tools = {
    "data_get_process": data_get_process,
    "path_finder": path_finder,
    "analyze_process": analyze_process,
    "draw_mat": draw_mat,
    "report_create": report_create,
}
~~~

**② 删除**原来第 347–353 行的 6 行明文配置常量（`DEFAULT_LLM_API_KEY` 等）。

**③ `run_agent` 函数里的配置读取**（原 375–378 行）改成：

~~~python
api_key = LLM_API_KEY
base_url = LLM_BASE_URL
model_id = LLM_MODEL_ID
os.environ.setdefault("TAVILY_API_KEY", TAVILY_API_KEY)
~~~

**④ 文件最底部**（`if __name__ == "__main__":`）保持不变，运行入口还是：

~~~bash
cd CMV1
python agent_main.py
~~~

> `__main__` 的语法说明见第 7.10 节。整份主程序改完先别急着跑大任务，先用第 5.6 节验证 import 能通。

### 5.6 改完必须同步改的 import（易错点清单！）

搬家/拆分后，**原来引用这些文件的代码必须跟着改**，否则报 `ModuleNotFoundError`。全项目就这几处，逐一检查：

| 文件 | 原来的 import | 改成 |
|---|---|---|
| `agent_main.py`（原 CMV测试agent.py） | `from data_get_process_tool_v2 import data_get_process` 等 5 行 | 见 5.5 ① |
| `ui/tools/mock_word_create.py`（第 25 行） | `from report_tool import report_create` | `from tools.report import report_create` |
| `tools/draw/draw_mat.py` 内部 | `import tables`、`import jobs`、`from matlab_backend import ...` | `from .tables import ...`、`from .jobs import ...`、`from .matlab_backend import ...` |
| `tools/draw/process_store.py` | `from draw_mat import ...` | `from .draw_mat import ...` |
| `test_draw_mat.py`（第 22 行） | `import draw_mat as dm` | `from tools.draw import draw_mat as dm`（并在运行前加 `sys.path` 或从 CMV1 目录跑） |

> 小知识：`from tools.report import report_create` 里 `tools.report` 中的 `tools` 是"包"，`report` 是包里的子包。只有从 `CMV1` 目录运行（或把 CMV1 加进 PYTHONPATH），Python 才能找到 `tools`。所以**运行一切脚本都要先 `cd CMV1`**。
> `ui/` 是独立的演示层，`ui/server.py` 只依赖 `ui/agent/mock_agent.py`，mock 工具不碰真实工具（唯一例外就是上面 mock_word_create.py 引用了 report_tool），所以 UI 基本不受影响。

### 5.7 顺手生成 requirements.txt（依赖清单）

在 `CMV1` 目录下运行（用你 PyCharm 的 Python 环境）：

~~~bash
pip freeze > requirements.txt
~~~

这会把当前环境所有已装的包列出来。如果想更精简，手动建一个（只写真正用到的）：

~~~text
openai
python-dotenv
flask
matplotlib
pillow
python-docx
python-pptx
pywin32
~~~

> `pip freeze` 是"我现在有什么"；上面手动清单是"项目需要什么"。新手用 `pip freeze` 最省事。

---

## 6. 第三步：.env 环境变量覆盖 API 密钥

### 6.1 为什么必须做

现在 `CMV测试agent.py` 第 348–353 行把密钥**明文写在代码里**。git 快照已经把这些行提交进历史了——所以**必须立刻改**，并且建议去模型平台后台把旧密钥吊销、签发新密钥（第 6.7 节）。

原理一句话：**代码里只写"我要读环境变量 LLM_API_KEY"，密钥本身放在 .env 文件里**。.env 不进 git，所以即使代码公开，密钥也不会泄露。

### 6.2 安装 python-dotenv

`python-dotenv` 是读取 .env 文件的小工具。在 `CMV1` 目录下：

~~~bash
pip install python-dotenv
~~~

### 6.3 创建 .env 和 .env.example

在**项目根目录**（不是 CMV1 里面！）新建文件 `.env`，内容（把密钥换成你自己的新密钥）：

~~~text
# ===== ChemMate V1 环境变量 =====
# 大模型 API（必填）
LLM_API_KEY=sk-把你的新密钥粘在这里
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=qwen3.8-max

# 联网搜索（可选）
TAVILY_API_KEY=tvly-把你的新密钥粘在这里
~~~

再复制一份叫 `.env.example`，把密钥位置换成占位符（`填你的密钥`），这份可以提交给 git 给别人看格式：

~~~text
LLM_API_KEY=填你的密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=qwen3.8-max
TAVILY_API_KEY=填你的密钥
~~~

> `.gitignore` 里已经写了 `.env`，所以 `git status` 永远不会出现 .env，想提交都提交不进去（除非强制）。`.env.example` 没有被忽略，可以提交。

### 6.4 创建 config.py（配置中心）

在 `CMV1/` 下新建 `config.py`，内容照抄：

~~~python
# -*- coding: utf-8 -*-
"""配置中心：所有密钥和参数都从环境变量读取（.env 文件提供）。"""
import os
from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录的 .env

LLM_API_KEY   = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL  = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL_ID  = os.environ.get("LLM_MODEL_ID", "qwen3.8-max")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
~~~

> 语法说明（小白版）：`os.environ.get("名字", 默认值)` = "去环境变量里找 `名字`，找到就用，找不到就用默认值"。所以 `.env` 里写了密钥 → 用 .env 的；没写 → 用默认的地址和模型名。**这就是"用 .env 覆盖原配置"的原理**。

### 6.5 修改主程序，删掉明文密钥

按第 5.5 节改 `agent_main.py`：
- 顶部加 `from dotenv import load_dotenv` 和 `load_dotenv()`（**必须在读取任何配置之前**）；
- 把原来 6 行 `DEFAULT_LLM_API_KEY = "sk-..."` 之类的明文常量**整段删除**；
- `run_agent` 里改用 `from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_ID`。

改完后，全项目搜一下还有没有明文密钥：

~~~bash
cd CMV1
python -c "import os; [print(f) for f in os.listdir('.') if f.endswith('.py')]"   # 确认没有 .env 内容
~~~

最直接的检查：在 PyCharm 里按 `Ctrl+Shift+F` 全局搜索 `sk-ws-`（你旧密钥的开头），结果应该**只剩 git 历史里**，代码文件里一条都没有。

### 6.6 验证 .env 生效

~~~bash
cd CMV1
python -c "from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_ID; print('密钥前缀:', LLM_API_KEY[:8] + '...'); print('地址:', LLM_BASE_URL); print('模型:', LLM_MODEL_ID)"
~~~

能打印出你 .env 里填的值就成功了。然后正常跑：

~~~bash
python agent_main.py
~~~

如果报错 `Incorrect API key` 之类，就是 .env 里的密钥填错了，检查有没有多余空格（`KEY=值` 的等号两边不要有空格）。

### 6.7 安全建议（重要）

1. **立刻去模型平台后台吊销旧密钥，签发新密钥**，新密钥只放进 .env（旧密钥已经进了 git 历史，等于公开了）。
2. 不要把 .env 截图、发给任何人、上传到任何地方。
3. `git status` 确认 .env 从未出现在列表里。
4. 以后换密钥 = 改 .env 一行，不用动任何代码。

---

## 7. Python 语法速查（代码小白专用）

> 下面每一节都结合你项目里的真实代码举例。**看不懂哪个语法就回来查哪节**。顺序是从最基础到常用进阶。

### 7.1 Python 文件长什么样

一个 .py 文件就是一段从上往下执行的程序。你项目里的文件一般长这样：

~~~python
# -*- coding: utf-8 -*-        ← 第 1 行：声明文件用 UTF-8 编码（中文不乱码）
"""这里是文件说明。"""           ← 文档字符串：解释这个文件是干嘛的

import os                      ← 导入工具包（见 7.8）
import json

def 函数名(参数):              ← 定义一个函数（见 7.7）
    ...函数内容...

if __name__ == "__main__":     ← "入口判断"（见 7.10）
    ...
~~~

**最重要的一条规则：Python 用"缩进"表示层级，不用花括号。**
`if`、`def`、`for` 后面以冒号 `:` 结尾，下一行必须缩进（PyCharm 会自动缩进 4 个空格）。缩进错了会报 `IndentationError`。

### 7.2 变量与数据类型

变量 = 给数据起个名字，**不用声明类型**，直接赋值：

~~~python
model = "qwen3.8-max"        # 字符串 str（带引号）
temperature = 78.5           # 小数 float
count = 3                    # 整数 int
ok = True                    # 布尔 bool（True / False，首字母大写）
nothing = None               # 空值 None（表示"没有"）
~~~

你项目里真实例子（CMV测试agent.py 第 349–353 行）：

~~~python
DEFAULT_LLM_API_KEY = "sk-..."      # 字符串
DEFAULT_LLM_BASE_URL = "https://..."  # 字符串
~~~

### 7.3 字符串和 f-string

字符串用单引号 `'环己烷'` 或双引号 `"S5"` 都行，混着用可以避免转义麻烦。

**f-string 是"会算数的字符串"**：字符串前面加 `f`，里面用 `{变量}` 就能把变量值插进去。你项目里大量使用，比如 data_get_process_tool_v2.py：

~~~python
name = "B1"
print(f"设备 {name} 的类型是 RStoic")
# 输出：设备 B1 的类型是 RStoic
~~~

还可以在花括号里做格式化：`f"{detail['block']:<4}"` 表示"把 block 的值放进来，左对齐占 4 个字符宽度"，用来对齐打印。

### 7.4 列表和字典（最常用的两种容器）

**列表** = 一串数据，用方括号 `[]`：

~~~python
streams = ["S5", "S10"]     # 创建
streams[0]                  # 取第 1 个 → "S5"（下标从 0 开始！）
streams.append("S12")       # 末尾加一个 → ["S5", "S10", "S12"]
len(streams)                # 长度 → 3
~~~

**字典** = 键值对，用花括号 `{}`，像查字典一样按"键"取值。你项目里到处都是，比如工具返回结果：

~~~python
result = {"success": True, "error": "流程有报错", "errors": ["B7"]}

result["success"]           # 取键 success 的值 → True
result.get("success")       # 推荐：取不到返回 None，不会报错
result.get("warning", "无") # 取不到时给默认值 → "无"
result["errors"]            # → ["B7"]
~~~

遍历字典（analyzer_tool.py 里常见）：

~~~python
for key, value in result.items():
    print(key, value)
~~~

### 7.5 条件判断 if / elif / else

~~~python
if result.get("success"):          # 条件是 True 就进来
    print("成功了")
elif result.get("status") == "error":   # 否则再看这个条件
    print("流程有报错")
else:                              # 都不满足
    print("其他情况")
~~~

注意：`==` 是比较（相等吗），`=` 是赋值（把值存进去）。**两者完全不同，别写混。** 还有 `!=`（不相等）、`and`（且）、`or`（或）、`not`（取反）。

### 7.6 循环 for / while

**for**：遍历列表/字典/字符串，最常用：

~~~python
for stream in ["S5", "S10"]:
    print(stream)              # 依次打印 S5、S10

for i in range(5):             # range(5) = 0,1,2,3,4
    print(i)

for detail in result["block_details"]:   # 你项目里遍历设备列表
    print(detail["real_type"])
~~~

**while**：条件成立就一直循环（你主程序里的主循环就是这种）：

~~~python
i = 0
while i < max_rounds:          # 只要 i < 20 就继续
    ...                        # 干一件事
    i = i + 1                  # 别忘了让条件最终变 False，否则死循环
~~~

### 7.7 函数 def（最重要的语法之一）

函数 = 把一段代码包起来，起个名字，以后反复调用。

~~~python
def 函数名(参数1, 参数2):
    第一行代码
    return 结果          # 把结果"交出去"；没有 return 就返回 None
~~~

你项目里的真实例子：

~~~python
def path_finder(filename: str):        # 参数 filename，冒号后面是类型说明（可写可不写）
    user_home = os.path.expanduser("~")
    ...
    return file_path                   # 返回找到的路径

def analyze_process(component=None, change_threshold=0.05):  # 默认参数：不传就用默认值
    ...
~~~

**默认参数**很常用：调用时可以不传，比如 `analyze_process()` 就等价于 `analyze_process(component=None, change_threshold=0.05)`。

**关键字参数**：调用时写 `函数名(参数名=值)`，可以只传想传的：

~~~python
draw_mat(plot_type="stream_tp", streams=["S5", "S10"])
~~~

你主程序里还有 `**kwargs`：意思是"把剩下的参数打包成一个字典"。

### 7.8 import 导入（三种写法）

import = 把别的文件/包里的东西拿过来用：

~~~python
import os                          # 方式1：导入整个模块，用 os.xxx 调用
import json

from draw_mat import draw_mat      # 方式2：只导入某个名字，直接用
from report_tool import report_create, build_sections_from_results   # 一次导多个

from .basic_checks import check_process   # 方式3：相对导入（点号=当前包，拆包后常用）
~~~

方式 1 用 `模块名.东西`，方式 2 直接用 `东西`。报 `ModuleNotFoundError` = 找不到这个模块（没装/路径不对/文件名写错）。

### 7.9 类 class（面向对象）

类 = 把"数据 + 操作这些数据的函数"打包成一个模板。你项目里的 `OpenAICompatibleClient` 就是类：

~~~python
class OpenAICompatibleClient:                  # 定义类
    def __init__(self, model, api_key, base_url):   # 构造方法：创建对象时自动执行
        self.model = model                      # self.xxx = 把这个值存进"这个对象"里
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt, system_prompt):  # 方法：类的函数
        ...调用大模型...
        return answer
~~~

使用：

~~~python
llm = OpenAICompatibleClient(model=model, api_key=api_key, base_url=base_url)  # 创建对象
answer = llm.generate(prompt, system_prompt)    # 调用方法
~~~

要点：
- `__init__` 是"构造方法"，创建对象时自动调用，用来初始化。
- `self` 指"当前这个对象自己"，方法里访问对象的数据必须用 `self.xxx`。
- 名字前后各两个下划线 `__xxx__` 是 Python 的特殊方法，别乱改。

### 7.10 模块、包和 `__main__`

- **模块** = 一个 .py 文件。
- **包** = 一个带 `__init__.py` 的文件夹，里面可以装多个模块。`tools/analyze/` 就是一个包。
- `if __name__ == "__main__":` 是"入口判断"：**只有直接运行这个文件时才执行**；如果这个文件是被别人 import 的，就不执行。每个项目都有且只有一个入口文件，你项目里就是 `CMV测试agent.py` 底部：

~~~python
if __name__ == "__main__":
    run_agent(DEFAULT_PROMPT)
~~~

### 7.11 异常处理 try / except

程序出错时不让它崩溃，而是"接住"错误继续处理：

~~~python
try:
    response = self.client.chat.completions.create(...)   # 可能出错的一步
except Exception as e:                                    # 出错就到这里
    print(f"调用出错: {e}")                               # e 是错误信息
    return "错误:调用语言模型服务时出错。"                   # 给出友好返回
~~~

`Exception` 是所有错误的统称。也可以细分（如 `except FileNotFoundError:`），新手先用 `Exception` 兜底即可。

### 7.12 文件和 JSON

**JSON** 是"文本格式的字典/列表"，你项目里工具之间传数据全靠它：

~~~python
import json

text = json.dumps(result, ensure_ascii=False)   # 字典 → 字符串（ensure_ascii=False 让中文不变成 \uXXXX）
data = json.loads(text)                         # 字符串 → 字典
~~~

**路径**（推荐用 pathlib，你项目里大量使用）：

~~~python
from pathlib import Path

p = Path("C:/Users/Fool/Desktop/ChemMateV1工作台/CMV1/reports")
p.mkdir(parents=True, exist_ok=True)   # 创建目录（不存在就建，已存在不报错）
f = p / "报告.docx"                    # 拼接路径（用 / 号，不是字符串加号）
f.exists()                             # 文件存在吗 → True/False
text = f.read_text(encoding="utf-8")   # 读文本
f.write_text(text, encoding="utf-8")   # 写文本
~~~

### 7.13 环境变量 os.environ

环境变量 = 操作系统层面的"全局设置项"。Python 里读写：

~~~python
import os

key = os.environ.get("LLM_API_KEY", "")   # 读：找不到就给默认值（第 6 节的核心）
os.environ["LLM_API_KEY"] = "xxx"         # 写（一般用不上）
~~~

`.env` 文件就是"把环境变量写在文件里"，`load_dotenv()` 一执行就把 .env 里的键值对灌进 `os.environ`，之后 `os.environ.get(...)` 就能读到。

### 7.14 在 PyCharm 里运行和调试

1. **运行**：打开 .py 文件，点编辑器右上角的绿色三角 ▶，或右键 → Run。也可以打开底部 Terminal 手动输入 `python 文件名.py`（注意要先 `cd` 到正确的目录）。
2. **调试**：在代码行号右侧点一下出现红点（断点），点绿色三角旁边的"虫子"图标（Debug），程序会停在断点处，你可以逐行看变量的值——**这是小白理解代码最好的工具**，强烈建议学会。
3. **改完代码立刻跑一遍**，养成习惯。

### 7.15 常见报错对照表（遇到别慌）

| 报错 | 意思 | 常见原因 |
|---|---|---|
| `SyntaxError` | 语法错误 | 少个冒号/括号/引号没配对 |
| `IndentationError` | 缩进错误 | 缩进不对齐（混用了 Tab 和空格等） |
| `NameError: name 'x' is not defined` | 名字没定义 | 变量/函数名拼错，或忘了 import |
| `ModuleNotFoundError` | 模块找不到 | 包没装（pip install）或路径不对、没 cd 到对的地方 |
| `ImportError` | 导入失败 | from 的东西不存在（名字拼错） |
| `FileNotFoundError` | 文件找不到 | 路径写错 |
| `TypeError` | 类型错误 | 比如字符串和数字直接相加 |
| `AttributeError: 'NoneType' object has no attribute ...` | 空值上取属性 | 函数返回了 None 但你当成正常结果用了（最常见！用 .get() 或加判断） |
| `json.decoder.JSONDecodeError` | JSON 解析失败 | 给的字符串不是合法 JSON |

**万能排查顺序**：①看报错最后一行 → ②看它指出的文件和行号 → ③检查那行的拼写和缩进 → ④不行就往上多看几行（真正出问题的地方常在报错点的上面）。

---

## 8. 全流程验证清单（做完打勾）

按顺序做，每完成一项就 `git add . && git commit -m "..."` 存个快照。

- [ ] 0. 确认 `git log --oneline` 能看到基线提交 76895e8
- [ ] 1. 建好 `tools/`、`agents/`、`memory/`、`legacy/` 目录（__init__.py 都在）
- [ ] 2. 小工具搬家完成：`git mv` 后 `git status` 显示 renamed
- [ ] 3. `tools/draw/` 归位完成，`python -c "from tools.draw import draw_mat; print('OK')"` 打印 OK
- [ ] 4. `tools/analyze/` 拆分完成，`python -c "from tools.analyze import analyze_process; print('OK')"` 打印 OK
- [ ] 5. `tools/data_get/` 拆分完成，`python -c "from tools.data_get import data_get_process; print('OK')"` 打印 OK
- [ ] 6. `tools/report/` 拆分完成，`python -c "from tools.report import report_create; print('OK')"` 打印 OK
- [ ] 7. `agents/` 三个文件切完，`python -c "from agents.llm_client import OpenAICompatibleClient; print('OK')"` 打印 OK
- [ ] 8. `memory/process_cache.py` 建好
- [ ] 9. `agent_main.py` 改造完成（import 全部指向新位置）
- [ ] 10. `ui/tools/mock_word_create.py` 的 import 已同步改
- [ ] 11. `pip install python-dotenv` 装好
- [ ] 12. 根目录 `.env`（真密钥）和 `.env.example`（占位符）建好
- [ ] 13. `config.py` 建好，`python -c "from config import LLM_API_KEY; print(LLM_API_KEY[:8])"` 能打印
- [ ] 14. 明文密钥已从代码删除，`Ctrl+Shift+F` 搜 `sk-ws-` 代码里搜不到
- [ ] 15. `requirements.txt` 生成
- [ ] 16. 完整跑一遍：`cd CMV1 && python agent_main.py` 能正常走完一个任务
- [ ] 17. 旧脚本已移入 `legacy/`，根目录清爽
- [ ] 18. 最后提交：`git add . && git commit -m "重构完成：拆分+目录重组+.env"`

---

## 9. Git 常用命令速查（新手版）

| 命令 | 作用 |
|---|---|
| `git status` | 看当前有什么改动（最常用） |
| `git log --oneline` | 看提交历史（一行一条） |
| `git add .` | 把所有改动放进"待提交区" |
| `git add 文件名` | 只放某个文件 |
| `git commit -m "说明"` | 把待提交区存成快照（永远记得写说明） |
| `git checkout -- 文件名` | 撤销某个文件的未提交改动（恢复到最后一次提交） |
| `git checkout -- .` | 撤销所有未提交改动（**回到基线**） |
| `git diff` | 看改动的具体内容 |
| `git stash` | 把当前改动临时藏起来（想先干别的再回来） |
| `git stash pop` | 把藏起来的改动取回来 |
| `git mv 旧路径 新路径` | 移动/重命名文件（保留历史） |
| `git rm 文件` | 删除文件 |
| `git branch` | 看分支（现在只有 main） |

**工作流口诀**：改代码 → `git status` 看 → `git add .` → `git commit -m "做了什么"` → 循环。改坏了 → `git checkout -- .` 回退。

> 如果提示找不到 git 命令：用完整路径 `C:/Program Files/Git/cmd/git.exe` 代替 `git`，或在 PyCharm Settings → Version Control → Git 里配置好。

---

## 10. 附录：常用命令速查

| 命令（在 PyCharm Terminal 里） | 作用 |
|---|---|
| `python --version` | 看 Python 版本（你的是 3.13） |
| `python 文件名.py` | 运行脚本（先 `cd` 到脚本所在目录） |
| `pip install 包名` | 安装包 |
| `pip freeze > requirements.txt` | 导出依赖清单 |
| `cd CMV1` | 进入 CMV1 目录（Windows 上也可以 `cd CMV1`） |
| `dir`（或 `ls`） | 看当前目录内容 |
| `cd ..` | 返回上一级目录 |

**最后一句鼓励**：你已经在没有任何版本控制的情况下把一条"取数→诊断→绘图→报告"的全链路跑通了 17 天，这本身就说明这套代码能工作。现在做的拆分和整理，只是让它"更好维护"而不是"能跑"。每完成一小步就提交一次，慢慢来，不会错。

> 遇到任何报错：先把报错最后一行 + 所在文件行号记下来，对照 7.15 表排查；排查不了就把报错贴给 AI 助手，让它结合本说明书帮你定位。


