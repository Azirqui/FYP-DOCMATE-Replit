from __future__ import annotations

import os
import re
from typing import Optional

import httpx

from .base import BaseLLMProvider, LLMConfig


class CodeT5Provider(BaseLLMProvider):
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        self._model_id = os.getenv(
            "HUGGINGFACE_MODEL_ID", "openai/gpt-oss-120b"
        )
        super().__init__(api_key, config)

    @property
    def default_model(self) -> str:
        return self._model_id

    @property
    def provider_name(self) -> str:
        return "codet5"

    def generate(self, prompt: str) -> str:
        code = self._extract_code(prompt)
        input_text = f"summarize python: {code}"
        api_url = f"https://router.huggingface.co/hf-inference/models/{self._model_id}"  # ✅ fixed
        headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json",  # ✅ add this too
    }
        payload = {
            "inputs": input_text,
            "parameters": {
                "max_length": 64,
                "num_beams": 4,
                "early_stopping": True,
            },
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, json=payload)

            if response.status_code == 503:
                body = response.json()
                if "estimated_time" in body:
                    import time
                    wait = min(body["estimated_time"], 30)
                    time.sleep(wait)
                    response = client.post(api_url, headers=headers, json=payload)

            if response.status_code != 200:
                raise RuntimeError(
                    f"HuggingFace API error ({response.status_code}): {response.text}"
                )

            result = response.json()

        if isinstance(result, list) and result:
            generated = result[0].get("generated_text", "")
        elif isinstance(result, dict):
            generated = result.get("generated_text", "")
        else:
            generated = str(result)

        return generated.strip()

    def generate_batch(self, code_snippets: list[str]) -> list[str]:
        return [self.generate(f"summarize python: {code}") for code in code_snippets]

    def is_available(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _extract_code(prompt: str) -> str:
        code_block = re.search(r"```python\s*\n(.*?)```", prompt, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        if "summarize python:" in prompt.lower():
            return prompt.split(":", 1)[-1].strip()

        return prompt.strip()
