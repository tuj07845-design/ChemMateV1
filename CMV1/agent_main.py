import re
import ast
import os
import json

from dotenv import load_dotenv
load_dotenv()  # ★ 第 1 件事：读取 .env（必须先于一切配置）
from tools.prrocess_data_get import data_get_process
from tools.path_finder import path_finder
from tools.analyze import analyze_process
from tools.draw_mat import draw_mat
from tools.report_creaate import report_create, build_sections_from_results
from tools.bash_tool import bash

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
    "bash_tool": bash_tool
}

# ============================================================
# Action 解析辅助（健壮版）
# ============================================================

def _extract_finish_answer(action_str):
    """
    从 "Finish[最终答案]" 中提取最终答案。

    模型输出的答案可能：
        - 跨多行（re 的 . 不匹配换行，旧版因此崩溃）
        - 含中文括号 / 嵌套 [ ]
        - 被截断（没有结尾 ]）

    这里不依赖正则的跨行能力，直接做字符串处理。
    """

    text = action_str

    # 去掉 "Finish" 前缀
    if text.startswith("Finish"):
        text = text[len("Finish"):]

    text = text.strip()

    # 去掉开头的 [
    if text.startswith("["):
        text = text[1:]

    # 去掉结尾的 ]（可能有空白）
    text = text.rstrip()

    if text.endswith("]"):
        text = text[:-1]

    return text.strip()


def _split_top_level(s):
    """
    按顶层逗号切分参数串。

    引号内、括号内的逗号不计入切分。
    例如：
        a="x,y", b='{"k": 1}'
    →   ['a="x,y"', "b='{\"k\": 1}'"]
    """

    parts = []
    depth = 0
    quote = None
    cur = []

    i = 0
    while i < len(s):

        ch = s[i]

        if quote:

            cur.append(ch)

            if ch == "\\":
                # 转义字符：跳过下一个字符
                if i + 1 < len(s):
                    cur.append(s[i + 1])
                    i += 1
            elif ch == quote:
                quote = None

        else:

            if ch in ('"', "'"):
                quote = ch
                cur.append(ch)
            elif ch in ("(", "["):
                # 圆括号/方括号都计入嵌套深度，
                # 保证 streams=["S5","S10"] 内部的逗号不被切分
                depth += 1
                cur.append(ch)
            elif ch in (")", "]"):
                depth -= 1
                cur.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(cur))
                cur = []
            else:
                cur.append(ch)

        i += 1

    if cur:
        parts.append("".join(cur))

    return parts


def _parse_value(raw):
    """
    把参数原始文本解析成 Python 值。

    支持：
        "环己烷" / '环己烷'      → 字符串（去掉引号）
        '{"success": true}'      → JSON 字符串（去掉单引号）
        "{...}"（内含未转义双引号）→ 去掉首尾引号，得到 JSON 字符串
        0.05 / 30                → 数字
        ["S5","S10"] / {"a":1}   → JSON 数组 / 对象（draw_mat 的 streams 等）
        其它裸词                  → 原样字符串
    """

    raw = raw.strip()

    # 引号包裹
    if (
        len(raw) >= 2
        and raw[0] in ('"', "'")
        and raw[-1] == raw[0]
    ):

        # 先试 ast.literal_eval（正确处理转义）
        try:
            return ast.literal_eval(raw)
        except Exception:
            pass

        # 再试 JSON（单引号 JSON 可能能解析）
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 兜底：去掉首尾引号，保留内部内容
        # （对 process_data="{...}" 这类未转义双引号 JSON 恰好有效）
        return raw[1:-1]

    # 数字
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass

    # JSON 数组 / 对象裸值（如 streams=["S5","S10"]）
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, (list, dict)):
            return parsed
    except Exception:
        pass

    # 裸词原样
    return raw


def _parse_tool_call(action_str):
    """
    解析工具调用：
        tool_name(k1="v1", k2='v2', k3=0.05)

    支持：
        - 单引号 / 双引号参数
        - 参数跨行
        - 值内含双引号的 JSON（单引号包裹）
        - 嵌套括号

    返回：
        (tool_name, kwargs)
        解析失败返回 None
    """

    name_match = re.match(
        r"(\w+)\s*\(",
        action_str
    )

    if not name_match:
        return None

    tool_name = name_match.group(1)

    rest = action_str[name_match.end():]

    # 找配对的右括号（感知引号与嵌套）
    depth = 1
    quote = None
    end = -1

    i = 0
    while i < len(rest):

        ch = rest[i]

        if quote:

            if ch == "\\":
                i += 2
                continue

            if ch == quote:
                quote = None

        else:

            if ch in ('"', "'"):
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        i += 1

    if end == -1:
        return None

    args_str = rest[:end]

    kwargs = {}

    for part in _split_top_level(args_str):

        part = part.strip()

        if not part:
            continue

        m = re.match(
            r"(\w+)\s*=\s*(.+)",
            part,
            re.DOTALL,
        )

        if not m:
            return None

        key = m.group(1)

        value = _parse_value(
            m.group(2)
        )

        kwargs[key] = value

    return tool_name, kwargs


def _observation_text(observation):
    """
    把工具返回结果转成 Observation 文本。

    要求：数据完整性优先（不压缩）。
    data_get 返回的完整 JSON（含每条流股的
    温度 / 压力 / 气相分率 / 质量流 / 摩尔流 / 摩尔分率）
    全部原样输出，供模型追踪组分、核对数值。

    analyze_process 的结果也是完整 JSON，
    模型可从中提取 findings / component_tracking。
    """

    if isinstance(observation, (dict, list)):

        return json.dumps(
            observation,
            ensure_ascii=False,
        )

    return str(observation)


# --- 1. 配置LLM客户端 ---
# 默认凭证（可被环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_ID 覆盖）

DEFAULT_PROMPT = "你好，10万吨环己烷.bkp 检查整个流程有无报错，如有报错，生成一份带有可视化数据图的报告给我,并附上保存路径"


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
        prompt_history.append(llm_output)

        # 解析并执行行动
        action_match = re.search(r"Action: (.*)", llm_output, re.DOTALL)
        if not action_match:
            observation = "错误: 未能解析到 Action 字段。请确保你的回复严格遵循 'Thought: ... Action: ...' 的格式。"
            observation_str = f"Observation: {observation}"
            _emit(f"{observation_str}\n" + "=" * 40)
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
                    # 同步给 draw_mat 的进程内缓存（双保险）
                    remember_process_data(observation)

        # 记录观察结果（dict 转完整 JSON，不压缩）
        observation_str = (
            "Observation: " + _observation_text(observation)
        )
        _emit(f"{observation_str}\n" + "=" * 40)
        prompt_history.append(observation_str)

        _emit("Tavily Key 是否读取到:", bool(os.environ.get("TAVILY_API_KEY")))

    return final_answer


if __name__ == "__main__":
    run_agent(DEFAULT_PROMPT)
