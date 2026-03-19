from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class AgentStep:
    agent_name: str
    role: str
    input_preview: str
    output: str
    duration_seconds: float
    step_number: int


@dataclass
class AgentTrace:
    steps: list[AgentStep] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    final_output: str = ""

    def add_step(self, step: AgentStep):
        self.steps.append(step)

    def to_dict(self) -> dict:
        return {
            "steps": [
                {
                    "step_number": s.step_number,
                    "agent_name": s.agent_name,
                    "role": s.role,
                    "input_preview": s.input_preview[:500],
                    "output": s.output,
                    "duration_seconds": round(s.duration_seconds, 2),
                }
                for s in self.steps
            ],
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "final_output": self.final_output,
        }


class Agent(ABC):
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    @abstractmethod
    def build_prompt(self, context: dict) -> str:
        pass

    def run(self, context: dict, provider) -> AgentStep:
        prompt = self.build_prompt(context)
        start = time.time()
        output = provider.generate(prompt).strip()
        duration = time.time() - start

        return AgentStep(
            agent_name=self.name,
            role=self.role,
            input_preview=prompt[:500],
            output=output,
            duration_seconds=duration,
            step_number=0,
        )
