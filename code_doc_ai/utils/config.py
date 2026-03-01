from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

import yaml


@dataclass
class LLMSettings:
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
        }


@dataclass
class OutputSettings:
    output_dir: str = "docs"
    include_uml: bool = True
    include_module_docs: bool = True
    include_project_overview: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "include_uml": self.include_uml,
            "include_module_docs": self.include_module_docs,
            "include_project_overview": self.include_project_overview,
        }


@dataclass
class UMLSettings:
    include_methods: bool = True
    include_attributes: bool = True
    max_methods: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "include_methods": self.include_methods,
            "include_attributes": self.include_attributes,
            "max_methods": self.max_methods,
        }


@dataclass
class Config:
    project_path: str = "."
    llm: LLMSettings = field(default_factory=LLMSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    uml: UMLSettings = field(default_factory=UMLSettings)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "llm": self.llm.to_dict(),
            "output": self.output.to_dict(),
            "uml": self.uml.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        llm_data = data.get("llm", {})
        output_data = data.get("output", {})
        uml_data = data.get("uml", {})
        
        return cls(
            project_path=data.get("project_path", "."),
            llm=LLMSettings(
                provider=llm_data.get("provider"),
                model=llm_data.get("model"),
                temperature=llm_data.get("temperature", 0.1),
            ),
            output=OutputSettings(
                output_dir=output_data.get("output_dir", "docs"),
                include_uml=output_data.get("include_uml", True),
                include_module_docs=output_data.get("include_module_docs", True),
                include_project_overview=output_data.get("include_project_overview", True),
            ),
            uml=UMLSettings(
                include_methods=uml_data.get("include_methods", True),
                include_attributes=uml_data.get("include_attributes", True),
                max_methods=uml_data.get("max_methods", 10),
            ),
        )
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        if config_path is None:
            config_path = Path("config.yaml")
        
        if not config_path.exists():
            return cls()
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        
        return cls.from_dict(data)
    
    def save(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            config_path = Path("config.yaml")
        
        with open(config_path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)


def get_api_key(provider: Optional[str] = None) -> Optional[str]:
    if provider == "groq":
        return os.getenv("GROQ_API_KEY")
    elif provider == "gemini":
        return os.getenv("GOOGLE_API_KEY")
    else:
        return os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_API_KEY")
