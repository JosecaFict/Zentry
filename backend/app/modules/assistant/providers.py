import logging

import httpx

logger = logging.getLogger("zentry.assistant")


class ProviderUnavailable(RuntimeError):
    pass


async def answer_with_provider(
    *,
    provider: str,
    model: str,
    api_key: str,
    system: str,
    history: list[dict[str, str]],
    timeout_seconds: float = 20.0,
) -> str:
    messages = [{"role": "system", "content": system}, *history]
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            if provider == "GROQ":
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_completion_tokens": 700,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            else:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [
                            {
                                "role": "model" if item["role"] == "assistant" else "user",
                                "parts": [{"text": item["content"]}],
                            }
                            for item in history
                        ],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1200},
                    },
                )
                response.raise_for_status()
                content = "".join(
                    part.get("text", "")
                    for part in response.json()["candidates"][0]["content"]["parts"]
                )
        if not content or not content.strip():
            raise ValueError("empty response")
        return content.strip()[:12000]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        logger.warning(
            "Assistant provider failed: provider=%s status=%s type=%s",
            provider,
            status,
            type(exc).__name__,
        )
        raise ProviderUnavailable from exc
