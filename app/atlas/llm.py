"""Ligacao com a LLM do ATLAS: Anthropic (principal) -> OpenAI (fallback).

Le as chaves de os.environ (nao acopla ao Settings estrito). Sem nenhuma
chave, llm_available() -> False e os endpoints devolvem 503 (fail-closed).
"""

import os

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_OPENAI_MODEL = "gpt-5.5"


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _anthropic(system: str, prompt: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("ATLAS_ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [t for b in resp.content if (t := getattr(b, "text", None))]
    return "\n".join(parts).strip()


def _openai(system: str, prompt: str, max_tokens: int) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("ATLAS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def ask_llm(system: str, prompt: str, max_tokens: int = 2000) -> str:
    """Tenta Anthropic; se falhar ou faltar chave, tenta OpenAI. Erro claro se nenhum."""
    errors: list[str] = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _anthropic(system, prompt, max_tokens)
        except Exception as e:  # noqa: BLE001
            errors.append(f"anthropic: {e}")
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return _openai(system, prompt, max_tokens)
        except Exception as e:  # noqa: BLE001
            errors.append(f"openai: {e}")
    if errors:
        raise RuntimeError("Nenhuma LLM funcional: " + "; ".join(errors))
    raise RuntimeError("Nenhuma chave de LLM configurada (ANTHROPIC_API_KEY/OPENAI_API_KEY)")
