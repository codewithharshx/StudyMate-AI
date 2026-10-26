"""
StudyMate AI - Gemini AI Service
--------------------------------
The only module that communicates with Google Gemini.
"""

import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

_client = None


class AIServiceError(Exception):
    """Friendly error raised when the Gemini service cannot complete a request."""
    pass


PROMPTS = {
    "summarize": {
        "system": (
            "You are an AI study assistant helping college students understand "
            "academic material. Be accurate, concise, and student-friendly."
        ),
        "user": (
            "Summarize the following study notes.\n\n"
            "Requirements:\n"
            "- Give a concise summary\n"
            "- Extract the most important points\n"
            "- List important terms\n"
            "- Do not invent information\n"
            "- Use simple student-friendly language\n\n"
            "Format the response with clear headings and bullet points:\n"
            "## Summary\n## Key Points\n## Important Terms\n\n"
            "Study notes:\n{content}"
        ),
    },
    "explain": {
        "system": (
            "You are a patient AI tutor helping college students understand "
            "technical concepts. Explain ideas accurately using simple language."
        ),
        "user": (
            "Explain the following concept in simple language.\n\n"
            "Concept:\n{content}\n\n"
            "Return the response with these headings:\n"
            "## Simple Definition\n"
            "## How It Works\n"
            "## Real-World Example\n"
            "## Simple Example\n"
            "## Key Takeaway\n\n"
            "Avoid unnecessarily complicated terminology."
        ),
    },
    "improve": {
        "system": (
            "You are an academic answer improvement assistant. Preserve the "
            "student's intended meaning and do not invent unsupported facts."
        ),
        "user": (
            "Improve the following student answer.\n\n"
            "Student answer:\n{content}\n\n"
            "Return the response with these headings:\n"
            "## Improved Answer\n"
            "## What Could Be Improved\n"
            "## Suggestions\n\n"
            "Keep the meaning of the student's original answer.\n"
            "Do not add unsupported facts.\n"
            "Use clear academic language."
        ),
    },
}


def _get_client():
    """Create the Gemini client only when it is first needed."""
    global _client

    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Reload .env in case it was created/updated after server startup
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise AIServiceError(
            "Gemini API is not configured. Please add GEMINI_API_KEY to the .env file."
        )

    try:
        _client = genai.Client(api_key=api_key)
        return _client
    except Exception as exc:
        logger.exception("Failed to initialize Gemini client: %s", type(exc).__name__)
        raise AIServiceError("Could not initialize the Gemini AI service.") from exc


def get_gemini_client():
    """Public shared client accessor for quiz and RAG services."""
    return _get_client()


def generate_with_gemini(user_prompt: str, system_instruction: str, max_output_tokens: int = 900,
                         temperature: float = 0.4) -> str:
    """Shared safe text-generation wrapper so services use one configuration path."""
    client = _get_client()
    try:
        response = client.models.generate_content(
            model=MODEL_NAME, contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_instruction,
                                               temperature=temperature,
                                               max_output_tokens=max_output_tokens),
        )
    except Exception as exc:
        logger.exception("Gemini API request failed: %s", type(exc).__name__)
        message = str(exc).lower()
        if "api key" in message or "authentication" in message or "unauthenticated" in message:
            raise AIServiceError("Gemini authentication failed. Please check your API key.") from exc
        if "quota" in message or "rate limit" in message or "resource exhausted" in message:
            raise AIServiceError("Gemini API quota/rate limit reached. Please try again later.") from exc
        if "timeout" in message:
            raise AIServiceError("Gemini took too long to respond. Please try again.") from exc
        if "connection" in message or "network" in message:
            raise AIServiceError("Could not connect to Gemini. Please check your internet connection.") from exc
        raise AIServiceError("The Gemini AI service returned an error. Please try again.") from exc
    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise AIServiceError("Gemini returned an empty response. Please try again.")
    return text.strip()


def generate_ai_response(mode: str, content: str) -> str:
    """Generate a response from Gemini using the selected structured prompt."""
    if mode not in PROMPTS:
        raise AIServiceError("Unknown study mode selected.")

    prompt = PROMPTS[mode]
    user_prompt = prompt["user"].format(content=content)
    return generate_with_gemini(user_prompt, prompt["system"], 900, 0.5)
