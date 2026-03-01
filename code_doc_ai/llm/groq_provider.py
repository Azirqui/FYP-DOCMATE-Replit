from __future__ import annotations

from typing import Optional

from .base import BaseLLMProvider, LLMConfig


class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        super().__init__(api_key, config)
        self._llm = None
    
    @property
    def default_model(self) -> str:
        return "llama-3.3-70b-versatile"
    
    @property
    def provider_name(self) -> str:
        return "groq"
    
    def _get_llm(self):
        if self._llm is None:
            from langchain_groq import ChatGroq
            self._llm = ChatGroq(
                model=self.config.model,
                api_key=self.api_key,
                temperature=self.config.temperature,
            )
        return self._llm
    
    def generate(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        
        llm = self._get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    
    def is_available(self) -> bool:
        return bool(self.api_key)
