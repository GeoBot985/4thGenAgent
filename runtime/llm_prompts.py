from __future__ import annotations



SYSTEM_PROMPT = (
    "You are a bounded helper inside an automation runtime.\n"
    "Only perform the requested transformation.\n"
    "Do not choose tools.\n"
    "Do not execute actions.\n"
    "Do not approve actions.\n"
    "Do not claim task completion.\n"
    "Return only the requested output format."
)


def build_summarize_prompt(text: str, max_words: str | int = 80) -> str:
    return (
        f"Summarize the following text in at most {max_words} words.\n"
        "Return plain text only.\n\n"
        f"Text:\n{text}"
    )


def build_extract_prompt(text: str, schema: str, fields: list[str] | None = None) -> str:
    field_text = ""
    if fields:
        field_text = f"Fields: {', '.join(fields)}\n"
    return (
        f"Extract the requested data for schema '{schema}'.\n"
        "Return JSON object only.\n"
        f"{field_text}\n"
        f"Text:\n{text}"
    )


def build_classify_prompt(text: str, labels: list[str]) -> str:
    return (
        "Classify the following text using exactly one of the allowed labels.\n"
        f"Allowed labels: {', '.join(labels)}\n"
        "Return JSON object only with label, confidence, and reason.\n\n"
        f"Text:\n{text}"
    )


def build_draft_prompt(instruction: str, context: str = "", tone: str = "plain") -> str:
    parts = [
        f"Instruction: {instruction}",
        f"Tone: {tone}",
    ]
    if context:
        parts.append(f"Context:\n{context}")
    parts.append("Return plain text only.")
    return "\n".join(parts)


def build_compare_prompt(left: str, right: str, criteria: str = "") -> str:
    criteria_text = f"Criteria: {criteria}\n" if criteria else ""
    return (
        "Compare the two text blocks.\n"
        f"{criteria_text}"
        "Return JSON object only with match, summary, and differences.\n\n"
        f"Left:\n{left}\n\nRight:\n{right}"
    )

