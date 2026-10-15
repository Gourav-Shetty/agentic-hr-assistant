"""App config from environment."""

import os


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


GROQ_API_KEY = _get("GROQ_API_KEY")
GEMINI_API_KEY = _get("GEMINI_API_KEY")
LLM_PROVIDER = _get("LLM_PROVIDER", "groq")
LLM_MODEL = _get("LLM_MODEL", "llama-3.3-70b-versatile")
EMBEDDING_MODEL = _get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHROMA_DIR = _get("CHROMA_DIR", "./data/chroma")
PDF_URL = _get(
    "PDF_URL",
    "https://raw.githubusercontent.com/Azure-Samples/azure-search-openai-demo/main/data/employee_handbook.pdf",
)
BACKEND_PORT = int(_get("BACKEND_PORT", "8000") or "8000")
FRONTEND_URL = _get("FRONTEND_URL", "http://localhost:5173")
CHECKPOINT_DB = _get("CHECKPOINT_DB", "./data/checkpoints.db")
