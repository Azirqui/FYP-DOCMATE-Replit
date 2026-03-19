from __future__ import annotations

import time
from typing import Optional

from .base import Agent, AgentTrace
from code_doc_ai.llm.base import BaseLLMProvider


class AgentEngine:
    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def run_pipeline(self, agents: list[Agent], initial_context: dict) -> AgentTrace:
        trace = AgentTrace()
        context = dict(initial_context)
        pipeline_start = time.time()

        for i, agent in enumerate(agents):
            step = agent.run(context, self.provider)
            step.step_number = i + 1
            trace.add_step(step)
            context[f"{agent.name.lower()}_output"] = step.output

        trace.total_duration_seconds = time.time() - pipeline_start
        if trace.steps:
            trace.final_output = trace.steps[-1].output

        return trace

    def run_doc_pipeline(
        self,
        project_outline: str,
        metrics_str: str,
        code_excerpts: dict[str, str],
        class_diagram: str = "",
    ) -> AgentTrace:
        from .doc_agents import PlannerAgent, AnalyzerAgent, WriterAgent, ReviewerAgent

        context = {
            "project_outline": project_outline,
            "metrics": metrics_str,
            "code_excerpts": code_excerpts,
            "class_diagram": class_diagram,
        }

        planner = PlannerAgent()
        analyzer = AnalyzerAgent()
        writer = WriterAgent()
        reviewer = ReviewerAgent()

        trace = AgentTrace()
        pipeline_start = time.time()
        step_num = 0

        step_num += 1
        planner_step = planner.run(context, self.provider)
        planner_step.step_number = step_num
        trace.add_step(planner_step)
        context["planner_output"] = planner_step.output

        step_num += 1
        analyzer_step = analyzer.run(context, self.provider)
        analyzer_step.step_number = step_num
        trace.add_step(analyzer_step)
        context["analyzer_output"] = analyzer_step.output

        step_num += 1
        writer_step = writer.run(context, self.provider)
        writer_step.step_number = step_num
        trace.add_step(writer_step)
        context["writer_output"] = writer_step.output

        step_num += 1
        reviewer_step = reviewer.run(context, self.provider)
        reviewer_step.step_number = step_num
        trace.add_step(reviewer_step)
        context["reviewer_output"] = reviewer_step.output

        step_num += 1
        context["review_feedback"] = reviewer_step.output
        final_writer = WriterAgent()
        final_writer.name = "FinalWriter"
        final_writer.role = "Produces the final documentation after incorporating review feedback"
        final_step = final_writer.run(context, self.provider)
        final_step.step_number = step_num
        trace.add_step(final_step)

        trace.total_duration_seconds = time.time() - pipeline_start
        trace.final_output = final_step.output

        return trace

    def run_module_pipeline(
        self,
        file_path: str,
        code_excerpt: str,
        outline: str,
    ) -> AgentTrace:
        from .doc_agents import AnalyzerAgent, WriterAgent, ReviewerAgent

        context = {
            "project_outline": outline,
            "metrics": "",
            "code_excerpts": {file_path: code_excerpt},
            "class_diagram": "",
            "single_module": True,
            "module_path": file_path,
        }

        analyzer = AnalyzerAgent()
        writer = WriterAgent()
        reviewer = ReviewerAgent()

        trace = AgentTrace()
        pipeline_start = time.time()
        step_num = 0

        step_num += 1
        analyzer_step = analyzer.run(context, self.provider)
        analyzer_step.step_number = step_num
        trace.add_step(analyzer_step)
        context["analyzer_output"] = analyzer_step.output

        step_num += 1
        writer_step = writer.run(context, self.provider)
        writer_step.step_number = step_num
        trace.add_step(writer_step)
        context["writer_output"] = writer_step.output

        step_num += 1
        reviewer_step = reviewer.run(context, self.provider)
        reviewer_step.step_number = step_num
        trace.add_step(reviewer_step)
        context["reviewer_output"] = reviewer_step.output

        step_num += 1
        context["review_feedback"] = reviewer_step.output
        final_writer = WriterAgent()
        final_writer.name = "FinalWriter"
        final_writer.role = "Produces the final module documentation after incorporating review feedback"
        final_step = final_writer.run(context, self.provider)
        final_step.step_number = step_num
        trace.add_step(final_step)

        trace.total_duration_seconds = time.time() - pipeline_start
        trace.final_output = final_step.output

        return trace
