# ChemMate V1 UI（真实 Agent 展示页）

Web 页面驱动**真实主程序**（CMV1/agent_main.py 的 run_agent）：
输入任务 → Aspen 取数 → 诊断 → MATLAB 绘图 → Word/PPT 报告，
页面实时展示 Agent 日志与产物。

## 运行

```bash
cd CMV1/ui
python Chem_Mate_V1.py          # 启动并自动打开 http://127.0.0.1:8765
```

不自动开浏览器：`set CHEMMATE_UI_NO_BROWSER=1`；改端口：`CHEMMATE_UI_PORT`。

## 依赖

`flask`（页面服务）；真实任务还需要：python-dotenv、openai、pywin32、matplotlib、python-docx、python-pptx，以及本机 Aspen Plus 与 MATLAB（可执行文件）。

## 架构

```
frontend/  原生 HTML/CSS/JS（无构建），400ms 轮询快照
server.py   Flask API：run/start、run/stop、run/state、runs/<id>/<file>、open
agent/real_agent.py   线程包装 run_agent：日志转发 + 产物登记
runs/      每次运行一个 <run_id>/ 目录：jobs/(图) + reports/(Word/PPT)
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/run/start` | `{task}` → `{run_id}`（真实 Agent 开始跑） |
| POST | `/api/run/stop` | `{run_id}` 请求停止（轮间生效） |
| GET | `/api/run/state?run_id=` | 全量快照（前端轮询） |
| GET | `/api/runs/<id>/<file>` | 运行产物（图 / 报告） |
| POST | `/api/open` | `{path}` 系统默认程序打开（限 runs 目录） |

## 注意

- Aspen 单实例：同一时刻只能跑一个任务；
- 停止按钮在每轮循环之间生效（非即时）；
- 首次真实运行要启动 Aspen，请耐心等待几分钟。
