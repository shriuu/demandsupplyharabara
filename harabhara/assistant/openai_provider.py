"""OpenAI chat-completions over plain HTTPS. Model, URL and limits come from config."""

from __future__ import annotations

import json
from urllib import error, request

from harabhara.assistant.provider import ProviderError
from harabhara.settings.schema import AssistantSettings


class OpenAIProvider:
    def __init__(self, cfg: AssistantSettings, api_key: str | None) -> None:
        if not api_key:
            msg = "OPENAI_API_KEY is not set"
            raise ProviderError(msg)
        self._cfg = cfg
        self._key = api_key

    def complete(self, system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": self._cfg.model,
                "temperature": self._cfg.temperature,
                "max_tokens": self._cfg.max_output_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        req = request.Request(
            f"{self._cfg.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with request.urlopen(req, timeout=self._cfg.timeout_s) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
        except error.HTTPError as exc:
            msg = f"OpenAI answered HTTP {exc.code}"
            raise ProviderError(msg) from None
        except (error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
            msg = "OpenAI could not be reached or sent an unreadable answer"
            raise ProviderError(msg) from None
        if not isinstance(text, str):
            msg = "OpenAI sent an unreadable answer"
            raise ProviderError(msg)
        return text
