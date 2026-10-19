# ============================================================
# 基础工具：analyze 包内部共用的取值 / 匹配辅助函数
# 全部为私有函数（_ 开头），只在本包内使用，不对外暴露
# ============================================================

from ..component_dicts import COMPONENT_ALIASES


# 宽松转 float：任意输入都不抛异常，转不动返回 None。
# bool 要提前拦掉 —— Python 里 True == 1，float(True) 会得到 1.0，
# 布尔值混进数值统计会污染结果。
def _number(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    # 剩余类型（以字符串为主）走 float()："10.5" 能转，"abc" / "" 抛异常。
    # 只接 TypeError / ValueError，其它异常应当冒出来暴露真实问题。
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# 从 data_get 的 {value, unit} 结构中取出数值；裸值原样返回。
# 只负责“取值”，不做类型转换 —— 转 float 是 _number 的职责。
def _value(data):
    if isinstance(data, dict):
        return data.get("value")

    return data


# 从 {value, unit} 结构中取出单位；裸值或键缺失都返回空字符串。
# 用 "" 而不是 None：下游做字符串拼接 / 判空时不用到处判 None。
def _unit(data):
    if isinstance(data, dict):
        return str(data.get("unit", ""))

    return ""


# 一步拿到可计算的数值：先 _value 取值，再 _number 宽松转 float。
# 需要“原文”时用 _value，需要参与运算时才走这里。
def _numeric_value(data):
    return _number(_value(data))


# 三级匹配找键名，命中返回原始键名，找不到返回 None。
# 一级：精确匹配（两边都 lower，大小写不敏感）
# 二级：别名表（中文名 → Aspen ID / 英文名）
# 三级：双向子串兜底 —— 可能误命中（"甲烷" 是 "十甲烷" 的子串），
#       所以放最后，前两级都不中才轮到它。
def _find_key(query, keys):
    q = str(query).strip().lower()

    if not q:
        return None

    # 1. 精确
    for key in keys:
        if str(key).lower() == q:
            return key

    # 2. 别名
    for alias in COMPONENT_ALIASES.get(q, []):
        for key in keys:
            if str(key).lower() == alias.lower():
                return key

    # 3. 子串兜底
    for key in keys:
        key_lower = str(key).lower()
        if q in key_lower or key_lower in q:
            return key

    return None
