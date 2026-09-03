import re
import ast
import os
import json

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




