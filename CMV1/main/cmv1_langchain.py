import sys
from pathlib import Path

# 本文件在 CMV1/main/ 下，而 tools / memory 以 CMV1/ 为导入根，
# 直接 python main/cmv1_langchain.py 时需要把 CMV1 补进 sys.path。
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
load_dotenv()  # ★ 第 1 件事：读取 .env（必须先于一切配置）
from tools_register import (
    analyze_process,
    bash,
    data_get_process,
    draw_mat,
    report_create,
)
from tools.path_finder_tool import path_finder
import os
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


AGENT_SYSTEM_PROMPT = """你是一个 Aspen Plus 化工模拟助手,拥有极深的化工专业知识，以及工程知识，你所有的想法都需符合工程与专业合理性。

# 任务
依据用户对自己的 Aspen 模型提出的问题，产出一篇能解决报错的报告（Word 或 PPT），
报告中必须写明至少 2 个可能的原因与对应办法。

# 工作流程要点
- 查验模拟有无报错：看 data_get_process 返回的 simulation_status（status=error 时 errors 里是出错设备）
- 用户没给文件绝对路径时，先用 path_finder 找文件；拿到路径后直接 data_get_process 读取全部数据
- analyze_process 和 draw_mat 会自动使用最近一次 data_get_process 的结果，不要重复取数
- 生成图表后再用 report_create 把结论和图片写进报告；结论文字由你自己组织
- bash 仅在其它工具不够用时兜底（例如对 path_finder 找到的文件做简单检查），其它情况禁用
"""



# ── 块① 模型：脑子 ──────────────────────────────
# 四个参数就是"连上哪家 API"：模型名 / 厂商 / 密钥 / 地址，全从 .env 读
model = init_chat_model(
    model = os.getenv("LLM_MODEL_ID"),
    model_provider="openai",
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
)
# ── 块② 工具：手 ────────────────────────────────
# 注册 = 把工具对象放进这个列表（import 只是搬进来，进列表才算注册）
tools = [
    path_finder,
    data_get_process,
    analyze_process,
    draw_mat,
    report_create,
    bash
]
# ── 块③ 记忆：本子 ──────────────────────────────
# InMemorySaver 是进程内存储，重启即忘；要持久化换 SqliteSaver
checkpointer = InMemorySaver()

# ── 块④ 代理：组装 ①+②+③ ───────────────────────
# 命令行用：带 checkpointer，多轮对话共享记忆
agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=AGENT_SYSTEM_PROMPT,
    checkpointer=checkpointer
)

# Dev Server / Studio 用：持久化由平台接管，图里不能自带 checkpointer，
# 否则 langgraph dev 会报 "includes a custom checkpointer" 并拒绝加载。
dev_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=AGENT_SYSTEM_PROMPT,
)

# ── 块⑤ 驱动：流式跑，逐个打印工具调用 ──────────
# config 是 checkpointer 的"对话编号"：同一个 thread_id 的多次调用共享记忆
config = {"configurable": {"thread_id": "cli-1"}}


def _to_text(content) -> str:
    """AI 消息的 content 可能是字符串，也可能是内容块列表。"""
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


def _fmt_args(args: dict, limit: int = 90) -> str:
    """把工具参数压成一行；长字符串和容器只留长度。"""
    items = []
    for key, value in (args or {}).items():
        if isinstance(value, str):
            value = value if len(value) <= 45 else value[:42] + "..."
        elif isinstance(value, (list, dict)):
            value = f"<{len(value)} 项>"
        items.append(f"{key}={value}")
    text = ", ".join(items)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _fmt_result(name: str, payload) -> str:
    """从工具返回里挑一行状态，不展开数据本体。"""
    if not isinstance(payload, dict):
        return str(payload)[:80]
    if payload.get("success") is False:
        reason = (
            payload.get("message")
            or payload.get("error")
            or payload.get("stderr")
            or "未知错误"
        )
        return f"失败: {str(reason)[:100]}"
    if name == "data_get_process":
        status = (payload.get("simulation_status") or {}).get("status", "unknown")
        return (
            f"流股 {payload.get('stream_count')} / 设备 {payload.get('block_count')}"
            f" / 连接 {payload.get('connection_count')} / 模拟 {status}"
        )
    if name == "analyze_process":
        summary = payload.get("summary") or {}
        return f"error {summary.get('error_count')} / warning {summary.get('warning_count')}"
    for key in ("file_path", "image_path", "returncode"):
        if payload.get(key) not in (None, ""):
            return str(payload[key])
    return "完成"


def run(task: str) -> str:
    """把任务交给 agent，边跑边打工具调用，返回最终回答。"""
    started: dict[str, tuple[str, float]] = {}
    answer = ""
    step = 0

    try:
        for chunk in agent.stream(
            {"messages": [HumanMessage(task)]},
            config=config,
            stream_mode="updates",
        ):
            for update in chunk.values():
                if not isinstance(update, dict):
                    continue
                for msg in update.get("messages") or []:
                    if isinstance(msg, AIMessage):
                        text = _to_text(msg.content).strip()
                        if text:
                            print(f"  · {text[:150]}", flush=True)
                        for call in msg.tool_calls or []:
                            step += 1
                            name = call.get("name") or "工具"
                            started[call.get("id") or f"step-{step}"] = (name, time.time())
                            print(
                                f"\n[{step}] {name}({_fmt_args(call.get('args'))})",
                                flush=True,
                            )
                        if not msg.tool_calls and text:
                            answer = text
                    elif isinstance(msg, ToolMessage):
                        name = msg.name or "工具"
                        _, begin = started.pop(msg.tool_call_id, (name, time.time()))
                        # 同一批并行调用的工具一起返回，共享同一个耗时，不挂在单个工具上
                        batch = update.get("messages") or []
                        spent = f"{time.time() - begin:.1f}s  " if len(batch) == 1 else ""
                        try:
                            payload = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                        except (TypeError, ValueError):
                            payload = msg.content
                        ok = msg.status != "error" and not (
                            isinstance(payload, dict) and payload.get("success") is False
                        )
                        print(
                            f"    {'✓' if ok else '×'} {spent}{_fmt_result(name, payload)}",
                            flush=True,
                        )
    except Exception as exc:
        print(f"\n[运行失败] {type(exc).__name__}: {exc}", flush=True)
        return ""

    print("\n回答 >", flush=True)
    print(answer or "（模型没有给出文字回答）", flush=True)
    return answer
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("ChemMate V1 Agent 已启动。")
    print("输入任务后回车执行；直接回车重输；输入 q 退出。")
    while True:
        task = input("任务 > ").strip()
        if not task:
            continue
        if task.lower() in ("q", "quit", "exit"):
            print("再见！")
            break
        run(task)



