import json
import uuid
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def new_session():
    """开始一个新会话，返回 session_id。"""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = stamp + "_" + uuid.uuid4().hex[:6]
    return session_id


def _log_path(session_id):
    return RUNS_DIR / ("session_" + session_id + ".jsonl")


def record(session_id, role, content):
    """记一条记录。role 取值：user / thought / action / observation / result。"""
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session": session_id,
        "role": role,
        "content": content,
    }
    path = _log_path(session_id)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_session(session_id):
    """读回一个会话的全部记录（列表，每条是 dict）。"""
    path = _log_path(session_id)
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def last_answers(session_id, n=3):
    """取最近 n 条最终答案（role=result），供下次任务参考。"""
    records = load_session(session_id)
    answers = [r["content"] for r in records if r.get("role") == "result"]
    return answers[-n:]