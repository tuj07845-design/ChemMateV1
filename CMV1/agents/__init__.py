import re
import ast
import os
import json

from dotenv import load_dotenv
load_dotenv()  # 第 1 件事：读 .env

# ---- 工具层（用你的实际目录名！）----
from tools.process_data_get import data_get_process
from tools.path_finder_tool import path_finder
from tools.analyze import analyze_process
from tools.draw_mat import draw_mat
from tools.report_create import report_create, build_sections_from_results
from tools.bash_tool import bash

# ---- Agent 层 ----
from agents.llm_client import OpenAICompatibleClient
from agents.action_parser import _extract_finish_answer, _parse_tool_call, _observation_text
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