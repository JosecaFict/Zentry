import httpx


class SpeechTranscriptionError(RuntimeError):
    """Raised when the speech provider cannot return a usable transcript."""


class GroqSpeechTranscriber:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 45.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def transcribe(self, filename: str, content_type: str, content: bytes) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (filename, content, content_type)},
                    data={
                        "model": self.model,
                        "language": "es",
                        "response_format": "json",
                        "temperature": "0",
                    },
                )
                response.raise_for_status()
                text = str(response.json().get("text", "")).strip()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise SpeechTranscriptionError("speech provider failure") from exc
        if not text:
            raise SpeechTranscriptionError("empty transcription")
        return text
