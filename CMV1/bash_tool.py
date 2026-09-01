# bash_tool.py
import subprocess
from pathlib import Path

# 只允许在这个目录下跑，避免乱删系统文件
WORK_ROOT = Path(r"C:\Users\Fool\Desktop\ChemMateV1工作台").resolve()

# 禁止的危险命令（可再加）
BLOCK = ("rm -rf", "del /s", "format", "shutdown", "reg delete", "Remove-Item -Recurse")


def bash(command: str, timeout: int = 60) -> dict:
    """
    在工作台目录执行一条 shell 命令。
    Agent 只应传简单命令，例如：dir、python xxx.py
    """
    cmd = (command or "").strip()
    if not cmd:
        return {"success": False, "stdout": "", "stderr": "命令为空", "returncode": -1}

    low = cmd.lower()
    for bad in BLOCK:
        if bad.lower() in low:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"禁止命令: {bad}",
                "returncode": -1,
            }

    try:
        # Windows 用 powershell；若你更习惯 cmd，可改成 ["cmd", "/c", cmd]
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            cwd=str(WORK_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "success": proc.returncode == 0,
            "stdout": (proc.stdout or "")[:8000],
            "stderr": (proc.stderr or "")[:4000],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"超时({timeout}s)", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}