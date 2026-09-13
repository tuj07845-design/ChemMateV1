# -*- coding: utf-8 -*-
"""ChemMate V1 UI 启动入口（真实模式：驱动 CMV1/agent_main.py）。

用法：
    python Chem_Mate_V1.py           # 启动并自动打开浏览器 http://127.0.0.1:8765
    set CHEMMATE_UI_NO_BROWSER=1 && python Chem_Mate_V1.py   # 不自动开浏览器
端口默认 8765，可用 CHEMMATE_UI_PORT 环境变量修改。

前提：.env 密钥有效、Aspen 与 MATLAB 可用（同 python agent_main.py 命令行）。
"""

from __future__ import annotations

import os
import threading
import webbrowser

from server import create_app

PORT = int(os.environ.get("CHEMMATE_UI_PORT", "8765"))
NO_BROWSER = os.environ.get("CHEMMATE_UI_NO_BROWSER") == "1"


def main() -> None:
    app = create_app()
    url = f"http://127.0.0.1:{PORT}"
    if not NO_BROWSER:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"* ChemMate V1 UI (Real Agent) -> {url}   Ctrl+C 退出")
    app.run(host="127.0.0.1", port=PORT, debug=False)


if __name__ == "__main__":
    main()
