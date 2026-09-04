# ChemMate V1 · AI 化工流程助手

> 输入自然语言任务，Agent 自主调度工具，驱动 **Aspen Plus** 取数、**MATLAB** 绘图、自动生成 **Word/PPT** 诊断报告的化工智能体系统。

![License: Non-Commercial](https://img.shields.io/badge/License-Non--Commercial-lightgrey.svg)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)

## ✨ 功能特性

- **Agent 全自主闭环**：用户任务 → Agent 推理决策（无硬编码流程）→ 工具链执行 → 结论与报告
- **Aspen Plus 数据引擎**：流股 / 设备 / 拓扑 / 模拟状态一键读取，字段带单位（C、bar、kg/hr…）；**兼容 .bkp 与 .apwz**（归档自动解包）
- **MATLAB 专业绘图**：物流组成 / 温度压力 / 组分追踪 / 衡算校核 四种图
- **中文报告自动生成**：Word 与 PPT，内嵌 MATLAB 图（宋体/黑体规范排版）
- **三层记忆**：进程缓存（工具间数据共享）+ 会话记录（JSONL 全链路回放）
- **Web 展示页**：实时驱动真实 Agent，动态展示每一轮推理与工具调用、图与报告产物
- **多模型可切换**：OpenAI 兼容接口，实测 qwen / glm / DeepSeek 系模型零代码切换

## 🏗 项目结构

```text
ChemMateV1/
├── CMV1/
│   ├── agent_main.py        # 主程序：Agent 推理循环 + 工具注册
│   ├── config.py            # 配置中心（读取 .env）
│   ├── agents/              # LLM 客户端 / Action 文本协议解析 / 系统提示词
│   ├── tools/
│   │   ├── process_data_get/   # Aspen 取数（COM + apwz 解包）
│   │   ├── analyze/            # 确定性诊断 / 组分追踪 / 变化分析
│   │   ├── draw_mat/           # 拆表 → job → MATLAB 出图
│   │   ├── report_create/      # Word / PPT 中文报告
│   │   ├── path_finder_tool.py # 模型文件定位
│   │   └── bash_tool.py        # 受限命令执行
│   ├── memory/              # 进程缓存 / 会话记忆（JSONL）
│   ├── ui/                  # Web 展示页（Flask + 原生前端，真实引擎）
│   ├── runs/                # 运行会话记录（不入库）
│   └── requirements.txt     # 依赖清单
├── 文档/                    # 全套开发与验收文档（重构/记忆/Git/GitHub/验收报告…）
├── legacy/                  # 早期版本归档
├── .env.example             # 环境变量模板
└── README.md
```

## 🚀 快速开始

### 环境要求

- Windows + Python 3.13
- Aspen Plus（本机安装并激活，提供 .bkp 或 .apwz 模型文件）
- MATLAB（R2025b，Python 3.13 兼容；或配置 `CHEMMATE_MATLAB_BIN`）
- 任一 OpenAI 兼容大模型 API

### 安装与配置

```bash
pip install -r CMV1/requirements.txt
cp .env.example .env        # 填入你的密钥与模型（.env 永不入库）
```

.env 关键项：

```env
LLM_API_KEY=你的密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_ID=qwen3.8-max    # 可换 glm-5.2 / deepseek-v4-flash 等
TAVILY_API_KEY=你的密钥      # 可选，联网搜索
```

### 命令行使用（实时输入任务）

```bash
cd CMV1
python agent_main.py
# 输入：检查 10万吨环己烷.bkp 全流程有无报错，如有则生成带图的 Word 报告
# 输入 q 退出
```

### Web 展示页

```bash
cd CMV1/ui
python Chem_Mate_V1.py       # 自动打开 http://127.0.0.1:8765
```

页面左侧实时长出 Agent 每轮动作卡片，右侧滚动完整日志，完成后展示结论、MATLAB 图与报告文件。

## 🔬 端到端示例

任务：*对 Aspen学习录 下三个模型（混合分离 / 乙醇-水 / 转化率反应）逐一分析并出综合报告*

Agent 实际执行链：`data_get_process(×3, apwz 自动解包) → analyze_process → draw_mat → report_create`，全程自动，报告落盘后提供路径。会话全流程记录于 `runs/session_*.jsonl`。

## 📐 设计要点

- **Tool 即服务**：每个工具包独立、结构化返回（success/error/message），经 `tools/*/__init__.py` 只暴露 1–2 个入口
- **Agent 即总控**：主循环读 LLM 的 Thought/Action，动态决定调用哪个工具、传什么参数、何时收尾
- **配置零硬编码**：模型、密钥、产物目录全部走 `.env` / 环境变量（`CHEMMATE_JOBS_DIR`、`CHEMMATE_REPORTS_DIR`…）
- **异常全链路可识别**：文件缺失 / COM 失败 / MATLAB 失败 / 解析失败均结构化返回，绝不伪成功

## 📚 文档

完整开发历程、重构操作手册、记忆模块指南、Git/GitHub 说明书、UI 接入说明与 V1 工程化验收标准均在 [`文档/`](文档/) 目录。

## ⚠️ 说明

- 运行产物（jobs/reports/runs）不入库；密钥仅存于本地 `.env`
- Aspen Plus 为单实例：同一时间只跑一个任务
- 深度思考类模型在复杂决策轮耗时可达数分钟（模型特性），速度优化见验收报告后续优化清单

## 📜 致谢与许可

- 架构思路受 **Hello-Agents 教程**（[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)）启发；本仓库代码为独立实现，教程版权归原作者所有。
- 本项目以 **Non-Commercial License** 发布（见 [LICENSE](LICENSE)）：允许自由查看、学习、研究、个人使用与简历展示；**商业使用需作者书面许可**。
- 依赖组件均为 MIT/BSD/PSF 等宽松许可的开源库；Aspen Plus、MATLAB 为商业软件，运行需各自合法授权。

---

*ChemMate V1 —— AI × 化工流程工程化 Demo（2026）*