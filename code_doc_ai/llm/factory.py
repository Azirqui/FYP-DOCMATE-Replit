from __future__ import annotations

import os
from typing import Optional

from .base import BaseLLMProvider, LLMConfig
from .groq_provider import GroqProvider
from .gemini_provider import GeminiProvider
from .codet5_provider import CodeT5Provider


class LLMFactory:
    _providers = {
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "codet5": CodeT5Provider,
    }
    
    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ) -> Optional[BaseLLMProvider]:
        if provider_name and api_key:
            provider_class = cls._providers.get(provider_name.lower())
            if provider_class:
                return provider_class(api_key, config)
            return None
        
        if api_key and not provider_name:
            if api_key.startswith("gsk_"):
                return GroqProvider(api_key, config)
            elif api_key.startswith("AI") or len(api_key) == 39:
                return GeminiProvider(api_key, config)
            else:
                return GroqProvider(api_key, config)
        
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            return GroqProvider(groq_key, config)
        
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            return GeminiProvider(google_key, config)
        
        return None
    
    @classmethod
    def get_codet5(cls) -> Optional[CodeT5Provider]:
        hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
        if not hf_token:
            return None
        return CodeT5Provider(hf_token)

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    @classmethod
    def is_codet5_available(cls) -> bool:
        return bool(os.getenv("HUGGINGFACE_API_TOKEN"))

    @classmethod
    def list_providers(cls) -> list[str]:
        available = []
        if os.getenv("GROQ_API_KEY"):
            available.append("groq")
        if os.getenv("GOOGLE_API_KEY"):
            available.append("gemini")
        if os.getenv("HUGGINGFACE_API_TOKEN"):
            available.append("codet5")
        return available
