import json
import re
from typing import Any

import requests


SYSTEM_PROMPT = """You are a local dictation cleanup engine. Return only JSON.
Rules:
- Preserve the user's intended meaning.
- Do not add facts.
- Remove filler words, repeated starts, and explicit self-corrections.
- Preserve mixed Chinese and English.
- Preserve technical terms and configured hotwords.
- Match the target application tone when app context is available.
- Return only JSON with action and text."""


class QwenClient:
    def __init__(self, base_url: str, model: str, timeout_sec: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec

    def health(self) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": 'Return exactly this JSON: {"action":"insert","text":"ok"}',
                    }
                ],
            },
            timeout=5,
        )
        response.raise_for_status()
        response.json()
        return {
            "status": "available",
            "endpoint": f"{self.base_url}/chat/completions",
            "model": self.model,
        }

    def polish(
        self,
        raw_text: str,
        *,
        app_name: str | None = None,
        hotwords: list[str] | None = None,
    ) -> str:
        if not raw_text.strip():
            return raw_text

        user_payload = {
            "app": app_name or "unknown",
            "mode": "dictation",
            "raw_transcript": raw_text,
            "hotwords": hotwords or [],
        }
        request_body = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = _parse_json_object(content)
            text = parsed.get("text")
            return text if isinstance(text, str) and text.strip() else raw_text
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            return raw_text


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response")
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON was not an object")
    return parsed
