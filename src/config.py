import os
from dotenv import load_dotenv

load_dotenv()


def get_config(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


LLM_BASE_URL = get_config("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = get_config("LLM_API_KEY", "")
LLM_MODEL = get_config("LLM_MODEL", "deepseek-chat")
HF_TOKEN = get_config("HF_TOKEN", "")
PDF_FONT_PATH = get_config("PDF_FONT_PATH", "")
