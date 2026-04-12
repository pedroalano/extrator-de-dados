"""Utilitários partilhados para prompts enviados a LLMs."""


def truncate_llm_user_prompt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars // 2] + "\n...[truncado]...\n" + text[-max_chars // 2 :]
