# ChemMate V1 UI（Mock 演示版）

Agent 控制台：左侧输入任务 → 中间 Workflow 卡片实时推进 → 右侧 Tool Console 日志 →
底部 Result 展示股流数据 / MATLAB 图 / Word·PPT 报告。

**当前为 Mock 模式**：未接入主程序与真实 Aspen/MATLAB，Tool 全部为模拟实现，
但 Tool 接口与未来真实 Tool 完全一致，替换时 UI 与 server 零改动。

## 运行

```bash
cd CMV1/ui
python run_server.py          # 启动后自动打开浏览器 http://127.0.0.1:8765
```

依赖：`flask`、`matplotlib`（缺失时 `pip install flask matplotlib`）。
不自动开浏览器：`set CHEMMATE_UI_NO_BROWSER=1`。改端口：`CHEMMATE_UI_PORT`。

## 目录

```
ui/
├── run_server.py        启动入口
├── server.py            Flask API（run/state/stop/report/redraw/open）
├── agent/
│   └── mock_agent.py    编排：任务解析 → 4 个 Tool → 分析 → 完成（状态机 + 日志 + 快照）
├── tools/
│   ├── base.py          Tool 接口约定（execute(task, context, log, stop) → ToolResult）
│   ├── mock_path_finder.py   定位 .bkp（Mock）
│   ├── mock_data_get.py      读取股流 T/P/流量/组成（Mock，数值 10 万吨环己烷量级）
│   ├── mock_draw_mat.py      出图（matplotlib 生成，PIL 兜底）
│   └── mock_word_create.py   报告（直接复用 CMV1/report_tool.py，中文排版）
├── frontend/            原生 HTML/CSS/JS（无构建）
└── runs/                每次运行一个 run_id 目录（图 + 报告）
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/run/start` | `{task}` → `{run_id}` |
| POST | `/api/run/stop` | `{run_id}` 请求停止 |
| GET | `/api/run/state?run_id=` | 全量快照（前端 400ms 轮询） |
| POST | `/api/report` | `{run_id, report_type: docx\|pptx}` 生成报告 |
| POST | `/api/redraw` | `{run_id}` 重新绘图 |
| GET | `/api/runs/<id>/<file>` | 运行产物 |
| POST | `/api/open` | `{path}` 系统默认程序打开（限 runs 目录） |

## 接入真实 Tool 的方式（UI 不改）

1. 新建 `tools/real_data_get.py`，继承 `tools.base.ToolBase`：
   - `execute(task, context, log, stop)` 内部调用 `CMV1/data_get_process_tool_v2.py`；
   - 过程中用 `log("Tool: data_get", "✓ Aspen started", ok=True)` 打点；
   - 收到 `stop.is_set()` 时尽快终止（抛 `ToolStopped`）；
   - 返回 `ToolResult(success, message, data)`，`data` 写入 context 供后续 Tool 使用
     （约定键：`model_path` / `stream` / `figure_path` / `reports`）。
2. 在 `agent/mock_agent.py` 的 `TOOL_REGISTRY` 里把 Mock 换成 Real。
3. 完成。`server.py`、`frontend/` 均不需要改动。

报告的 Word/PPT 排版由 `CMV1/report_tool.py` 负责
（宋体正文/黑体标题/1.5 倍行距/首行缩进两字符/表格跨页规则，修改处带 `# glm` 标记）。
