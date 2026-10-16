"""LLM wrapper: Groq primary, Gemini fallback, rule-based last resort."""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SYSTEM_HINT = "You are a helpful HR assistant. Answer using the provided context. Cite pages like [Page N]."


def active_provider() -> str:
    """groq | gemini | none — without leaking keys."""
    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "gemini"
    return "none"


DEPRECATED_MODELS = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-20b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama3-70b-8192": "openai/gpt-oss-20b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
}


def get_llm():
    """Return a chat model or None if no keys / libs available."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if groq_key:
        try:
            from langchain_groq import ChatGroq

            model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
            model = DEPRECATED_MODELS.get(model, model)
            return ChatGroq(
                model=model,
                api_key=groq_key,
            )
        except Exception:
            pass
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=gemini_key,
            )
        except Exception:
            pass
    return None


def generate(prompt: str, context: str = "") -> str:
    """Generate a reply. Falls back to rule-based answer when no LLM."""
    llm = get_llm()
    if llm is not None:
        try:
            full = f"{SYSTEM_HINT}\n\nContext:\n{context}\n\nQuestion: {prompt}"
            resp = llm.invoke(full)
            text = getattr(resp, "content", str(resp))
            if isinstance(text, list):
                text = " ".join(str(p) for p in text)
            return str(text).strip()
        except Exception:
            pass
    # Rule-based fallback (offline): echo context snippet or generic help.
    if context:
        snippet = context.strip().split("\n")[0][:500]
        return f"Based on the handbook: {snippet}"
    return (
        "I can help with HR questions (leave, benefits, performance reviews) "
        "or book a performance review session. What would you like to do?"
    )
