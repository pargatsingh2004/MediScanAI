"""Report-grounded chat operations using the existing safe analysis prompts."""

from backend.core.healthcare_intelligence.backend.workspace_analysis import (
    generate_chat_reply,
    humanize_reply,
)


def generate_reply(question, report, history=(), language="en"):
    """Answer from one report's context and the user's prior conversation."""
    question = str(question or "").strip()
    if not question:
        raise ValueError("A question is required.")
    return generate_chat_reply(question, report, history, language)


def rewrite_reply(message, language="en"):
    """Rewrite an assistant answer in the selected supported language."""
    message = str(message or "").strip()
    if not message:
        raise ValueError("A message is required.")
    return humanize_reply(message, language)
