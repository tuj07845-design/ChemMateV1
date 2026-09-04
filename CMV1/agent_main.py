import re
import ast
import os
import json

from dotenv import load_dotenv
load_dotenv()  # ★ 第 1 件事：读取 .env（必须先于一切配置）
from tools.process_data_get import data_get_process
from tools.path_finder_tool import path_finder
from tools.analyze import analyze_process
from tools.draw_mat import draw_mat
from tools.report_create import report_create, build_sections_from_results
from tools.bash_tool import bash
from memory.process_cache import remember_process_data,get_cached_process_data,get_history,clear
from memory.session_store import new_session,_log_path,record,load_session,last_answers

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

available_tools = {
    "data_get_process": data_get_process,
    "path_finder": path_finder,
    "analyze_process": analyze_process,
    "draw_mat": draw_mat,
    "report_create": report_create,
    "bash": bash,
}

# ============================================================
# Action 解析辅助（健壮版）
# ============================================================



def run_agent(task, max_rounds=20, stop_event=None, log=None):
    """真实 Agent 主循环（可复用入口）。

    参数：
        task         用户任务原文
        max_rounds   LLM 最大循环轮数
        stop_event   threading.Event，置位后在下一轮开始前中断（返回空串）
        log          日志回调 log(text)；为 None 时用 print

    返回：
        最终答案字符串（Finish 里的内容）；被 stop 中断或未 Finish 时返回 ""。

    说明：
        命令行直接运行本文件行为不变（见 __main__）；
        UI 后端可 import 本函数，把 log 接到前端日志、stop_event 接到停止按钮。
    """

    _emit = log if log is not None else print

    # ---- 会话记忆：开始新会话，记录用户请求 ----
    session_id = new_session()
    record(session_id, "user", task)
    prev = last_answers(session_id)
    if prev:
        _emit("引用上次任务结论: " + prev[-1])

    api_key = LLM_API_KEY
    base_url = LLM_BASE_URL
    model_id = LLM_MODEL_ID
    os.environ.setdefault("TAVILY_API_KEY", TAVILY_API_KEY)

    llm = OpenAICompatibleClient(
        model=model_id,
        api_key=api_key,
        base_url=base_url,
    )

    user_prompt = task
    prompt_history = [f"用户请求: {user_prompt}"]

    # 保存最近一次 data_get 的完整结果，analyze_process / draw_mat
    # 未显式传 process_data 时自动注入。
    _last_data_get_result = None

    final_answer = ""

    _emit(f"用户输入: {user_prompt}\n" + "=" * 40)

    # --- 主循环 ---
    for i in range(max_rounds):

        # 停止信号：下一轮开始前中断
        if stop_event is not None and stop_event.is_set():
            _emit("已收到停止请求，中断任务。")
            break

        _emit(f"--- 循环 {i + 1} ---\n")

        # 构建 Prompt
        full_prompt = "\n".join(prompt_history)

        # 调用 LLM 思考
        llm_output = llm.generate(full_prompt, system_prompt=AGENT_SYSTEM_PROMPT)
        # 截断多余的 Thought-Action
        match = re.search(
            r'(Thought:.*?Action:.*?)(?=\n\s*(?:Thought:|Action:|Observation:)|\Z)',
            llm_output,
            re.DOTALL,
        )
        if match:
            truncated = match.group(1).strip()
            if truncated != llm_output.strip():
                llm_output = truncated
                _emit("已截断多余的 Thought-Action 对")
        _emit(f"模型输出:\n{llm_output}\n")
        record(session_id, "thought", llm_output)
        prompt_history.append(llm_output)

        # 解析并执行行动
        action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
        if not action_match:
            observation = "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式。"
            observation_str = f"Observation: {observation}"
            _emit(f"{observation_str}\n" + "=" * 40)
            record(session_id, "observation", observation_str)
            prompt_history.append(observation_str)
            continue
        action_str = action_match.group(1).strip()

        if action_str.startswith("Finish"):
            final_answer = _extract_finish_answer(action_str)
            _emit(f"任务完成，最终答案: {final_answer}")
            break

        parsed = _parse_tool_call(action_str)

        if parsed is None:
            observation = (
                f"错误: 无法解析工具调用 '{action_str}'。"
                "请使用 function_name(arg_name=value) 格式，"
                "参数用引号包裹，JSON 参数用单引号包裹。"
            )
            observation_str = f"Observation: {observation}"
            _emit(f"{observation_str}\n" + "=" * 40)
            record(session_id, "observation", observation_str)
            prompt_history.append(observation_str)
            continue

        tool_name, kwargs = parsed

        if tool_name not in available_tools:
            observation = f"错误:未定义的工具 '{tool_name}'"
        else:
            # analyze_process / draw_mat 未显式传 process_data 时，
            # 自动注入最近一次 data_get 的完整结果
            if (
                tool_name in ("analyze_process", "draw_mat")
                and "process_data" not in kwargs
            ):
                if _last_data_get_result is None:
                    observation = (
                        "错误: 尚无 data_get_process 的返回数据。"
                        "请先调用 data_get_process(file_path=...) "
                        "读取流程数据。"
                    )
                else:
                    kwargs["process_data"] = _last_data_get_result
                    observation = available_tools[tool_name](**kwargs)
            else:
                try:
                    observation = available_tools[tool_name](**kwargs)
                except Exception as e:
                    observation = (
                        f"错误: 工具 {tool_name} 执行异常: " + str(e)
                    )

            # data_get 成功后保存完整结果（供 analyze 注入）
            if tool_name in ("data_get_process", "data_get_stream"):
                if (
                    isinstance(observation, dict)
                    and observation.get("success")
                ):
                    _last_data_get_result = observation
                    # 同步给 memory 的进程内缓存
                    remember_process_data(observation)

        # 记录观察结果（dict 转完整 JSON，不压缩）
        observation_str = (
            "Observation: " + _observation_text(observation)
        )
        record(session_id, "observation", observation_str)
        _emit(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)

        _emit(f"Tavily Key 是否读取到: {bool(os.environ.get('TAVILY_API_KEY'))}")

    # ---- 循环结束（Finish / 停止 / 轮数耗尽都走到这里）----
    if final_answer:
        record(session_id, "result", final_answer)
    else:
        record(session_id, "result", "（任务未完成：被停止或达到最大轮数）")

    return final_answer


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
        run_agent(task)