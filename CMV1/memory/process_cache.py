
_LAST_PROCESS_DATA = None
_HISTORY = []          # 最近 N 次取数历史（可选功能）


def remember_process_data(data, keep_history=False):
    """保存最近一次取数结果，返回原值（方便链式调用）。"""
    global _LAST_PROCESS_DATA
    _LAST_PROCESS_DATA = data
    if keep_history:
        _HISTORY.append(data)
        if len(_HISTORY) > 10:          # 最多留 10 条，防止内存膨胀
            _HISTORY.pop(0)
    return data


def get_cached_process_data():
    """取回最近一次结果；没有则返回 None。"""
    return _LAST_PROCESS_DATA


def get_history():
    """取历史列表（副本，防止外部误改）。"""
    return list(_HISTORY)


def clear():
    """清空缓存（任务开始前可调用，保证干净开始）。"""
    global _LAST_PROCESS_DATA
    _LAST_PROCESS_DATA = None
    _HISTORY.clear()