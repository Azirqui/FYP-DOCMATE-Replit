from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.1
    max_tokens: Optional[int] = None


class BaseLLMProvider(ABC):
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        self.api_key = api_key
        self.config = config or LLMConfig(model=self.default_model)
    
    @property
    @abstractmethod
    def default_model(self) -> str:
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
    
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
