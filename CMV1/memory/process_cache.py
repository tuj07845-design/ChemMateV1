# memory/process_cache.py
"""最近一次 data_get_process 结果的进程内缓存。

remember_process_data: 存(成功才存), 原样返回数据
get_cached_process_data: 取, 没有则返回 None
"""

_cached = None


def remember_process_data(data):
    global _cached
    if isinstance(data, dict) and data.get("success", True):
        _cached = data
    return data


def get_cached_process_data():
    return _cached
