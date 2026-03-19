from __future__ import annotations

from .base import Agent


class PlannerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Planner",
            role="Analyzes the project structure and creates a documentation plan"
        )

    def build_prompt(self, context: dict) -> str:
        outline = context.get("project_outline", "")
        metrics = context.get("metrics", "")
        class_diagram = context.get("class_diagram", "")

        code_files_section = ""
        excerpts = context.get("code_excerpts", {})
        if excerpts:
            file_list = ", ".join(excerpts.keys())
            code_files_section = f"\nFiles in project: {file_list}"

        return f"""You are a Documentation Planner agent. Your job is to look at a Python project
and create a structured plan for what documentation should be written.

PROJECT OUTLINE:
{outline}

PROJECT METRICS:
{metrics}
{code_files_section}

CLASS DIAGRAM (Mermaid):
```mermaid
{class_diagram}
```

Create a documentation plan with the following structure:

1. PROJECT SUMMARY: A 1-2 sentence description of what this project does
2. KEY TOPICS: List the most important things to document (main classes, core algorithms, data flow)
3. DOCUMENTATION SECTIONS: List the sections the final documentation should have, in order
4. AUDIENCE: Who is this documentation for (new developers, API consumers, etc.)
5. SPECIAL NOTES: Any design patterns, architectural decisions, or complex logic that needs extra explanation

Be specific and reference actual class/function names from the outline. Keep your plan concise but thorough."""


class AnalyzerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Analyzer",
            role="Deep-dives into the code to understand what each component does"
        )

    def build_prompt(self, context: dict) -> str:
        outline = context.get("project_outline", "")
        excerpts = context.get("code_excerpts", {})
        planner_output = context.get("planner_output", "")
        is_single_module = context.get("single_module", False)
        module_path = context.get("module_path", "")

        code_section = ""
        if is_single_module and module_path in excerpts:
            code_section = f"""CODE FOR {module_path}:
```python
{excerpts[module_path]}
```"""
        elif excerpts:
            code_parts = []
            for fp, code in excerpts.items():
                truncated = "\n".join(code.splitlines()[:80])
                code_parts.append(f"--- {fp} ---\n```python\n{truncated}\n```")
            code_section = "\n\n".join(code_parts)

        plan_section = ""
        if planner_output:
            plan_section = f"""
DOCUMENTATION PLAN (from Planner agent):
{planner_output}
"""

        return f"""You are a Code Analyzer agent. Your job is to study Python source code and
produce a detailed analysis of what each component does.

PROJECT OUTLINE:
{outline}
{plan_section}
{code_section}

Produce a detailed analysis with the following for each class and function:

1. PURPOSE: What does this component do? (1-2 sentences)
2. KEY LOGIC: What is the core algorithm or business logic?
3. INPUTS/OUTPUTS: What does it take in and return?
4. RELATIONSHIPS: How does it interact with other components?
5. DESIGN PATTERNS: Any patterns used (Factory, Singleton, Observer, etc.)

Also identify:
- The main entry points of the application
- Data flow: how data moves through the system
- Any error handling patterns
- External dependencies or integrations

Be thorough but concise. Use the actual names from the code."""


class WriterAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Writer",
            role="Writes polished Markdown documentation from the plan and analysis"
        )

    def build_prompt(self, context: dict) -> str:
        outline = context.get("project_outline", "")
        planner_output = context.get("planner_output", "")
        analyzer_output = context.get("analyzer_output", "")
        review_feedback = context.get("review_feedback", "")
        class_diagram = context.get("class_diagram", "")
        metrics = context.get("metrics", "")
        is_single_module = context.get("single_module", False)
        module_path = context.get("module_path", "")

        feedback_section = ""
        if review_feedback:
            feedback_section = f"""

REVIEWER FEEDBACK (incorporate this into your final version):
{review_feedback}

Important: Address every issue raised by the reviewer. This is your FINAL version."""

        if is_single_module:
            module_name = module_path.replace(".py", "").split("/")[-1]
            return f"""You are a Technical Writer agent. Write polished documentation for a single Python module.

MODULE: {module_path}

CODE ANALYSIS (from Analyzer agent):
{analyzer_output}
{feedback_section}

Write the documentation in Markdown with this structure:
- Start with: ## {module_name} Module
- Overview paragraph explaining what this module does
- Key Classes and Functions section with descriptions
- Usage Notes section covering important behaviors or edge cases
- Do NOT include the full source code

Write clearly and professionally. Be helpful to a developer seeing this code for the first time."""

        return f"""You are a Technical Writer agent. Write comprehensive project documentation in Markdown.

PROJECT OUTLINE:
{outline}

DOCUMENTATION PLAN (from Planner agent):
{planner_output}

CODE ANALYSIS (from Analyzer agent):
{analyzer_output}

PROJECT METRICS:
{metrics}

CLASS DIAGRAM (Mermaid):
```mermaid
{class_diagram}
```
{feedback_section}

Write the documentation in Markdown with this structure:

# Project Overview
What the project does and its purpose.

# Architecture
How the project is organized — modules, layers, and their responsibilities.

# Class Diagram
Include the Mermaid diagram in a fenced code block.

# Key Components
Detailed descriptions of the main classes and functions, grouped by module.

# Data Flow
How data moves through the system from input to output.

# Metrics
Summary of project statistics.

Write clearly and professionally. Use the analysis to provide accurate, detailed descriptions.
Do NOT make up features that aren't in the code."""


class ReviewerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Reviewer",
            role="Reviews generated documentation for accuracy, completeness, and quality"
        )

    def build_prompt(self, context: dict) -> str:
        outline = context.get("project_outline", "")
        writer_output = context.get("writer_output", "")
        is_single_module = context.get("single_module", False)

        scope = "module documentation" if is_single_module else "project documentation"

        return f"""You are a Documentation Reviewer agent. Your job is to review generated {scope}
and provide specific, actionable feedback.

ORIGINAL PROJECT OUTLINE (ground truth):
{outline}

GENERATED DOCUMENTATION (to review):
{writer_output}

Review the documentation and provide:

1. ACCURACY SCORE (1-10): Does the documentation accurately describe what the code does?
   - Flag any claims that don't match the code outline
   - Flag any invented features or components

2. COMPLETENESS SCORE (1-10): Does it cover all important components?
   - List any classes/functions from the outline that are missing from the docs
   - Note any sections that need more detail

3. CLARITY SCORE (1-10): Is it easy to understand?
   - Flag any confusing explanations
   - Suggest simpler wording where needed

4. SPECIFIC IMPROVEMENTS:
   - List exactly what should be added, removed, or rewritten
   - Be specific: "Add description of the X class" not "add more detail"

5. OVERALL QUALITY: One paragraph summary of the documentation quality.

Be constructive and specific. The Writer agent will use your feedback to produce the final version."""
