import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LLM_API_KEY   = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL  = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL_ID  = os.environ.get("LLM_MODEL_ID", "qwen3.8-max")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
