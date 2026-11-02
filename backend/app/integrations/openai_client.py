from openai import AsyncOpenAI

from backend.app.config import get_settings


def get_openai_client() -> AsyncOpenAI:
    """Create the OpenAI client from server-side environment configuration."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return AsyncOpenAI(api_key=settings.openai_api_key)
