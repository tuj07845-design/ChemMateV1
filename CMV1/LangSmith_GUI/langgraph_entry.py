"""LangGraph Dev Server / Studio 入口。

cmv1_langchain.py / tools_register.py 在 CMV1/main/ 下，
工具层又以 CMV1/ 为导入根（`from tools.xxx import ...`），
所以两个目录都要补进 sys.path。

这里不传 checkpointer：Dev Server 会按 thread 注入自己的存储。
"""

import sys
from pathlib import Path

_CMV1 = Path(__file__).resolve().parents[1]          # .../ChemMateV1工作台/CMV1
_MAIN = _CMV1 / "main"                               # cmv1_langchain.py / tools_register.py 所在目录
for _p in (str(_CMV1), str(_MAIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langchain.agents import create_agent  # noqa: E402

from cmv1_langchain import AGENT_SYSTEM_PROMPT, model, tools  # noqa: E402

agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=AGENT_SYSTEM_PROMPT,
)
