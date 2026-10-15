"""LLM wrapper: Groq primary, Gemini fallback, rule-based last resort."""

import os

SYSTEM_HINT = "You are a helpful HR assistant. Answer using the provided context. Cite pages like [Page N]."


def get_llm():
    """Return a chat model or None if no keys / libs available."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if groq_key:
        try:
            from langchain_groq import ChatGroq

            return ChatGroq(
                model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
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
