from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

llm = None
_llm_available = None


def is_llm_available() -> bool:
    global _llm_available
    if _llm_available is not None:
        return _llm_available
    
    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    _llm_available = bool(groq_key or google_key)
    return _llm_available


def get_llm():
    global llm
    if llm is not None:
        return llm
    
    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    
    if groq_key:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0.1,
        )
    elif google_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0.1,
        )
    else:
        return None
    
    return llm


function_prompt = ChatPromptTemplate.from_template(
"""You are an expert Python developer.

Write a concise, accurate docstring for the following Python function or method.

Requirements:
- Google-style docstring.
- Describe purpose, arguments, return value, and side effects (if any).
- If it is a method, consider 'self' and the class context implied by the code.
- Be strictly consistent with the code (no hallucinations).
- DO NOT include the function signature.
- DO NOT wrap the docstring in quotes. Return ONLY the inner text.

Code:
```python
{code}
```""")


class_prompt = ChatPromptTemplate.from_template(
"""You are an expert Python developer.

Write a concise, accurate docstring for the following Python class.

Requirements:
- Google-style docstring.
- Describe the purpose of the class, its main responsibilities, and important attributes or methods.
- Be strictly consistent with the code (no hallucinations).
- DO NOT include the class signature.
- DO NOT wrap the docstring in quotes. Return ONLY the inner text.

Code:
```python
{code}
```""")


module_prompt = ChatPromptTemplate.from_template(
"""You are an expert software engineer and technical writer.

You are given information about a single Python module.

File path: {path}

High-level outline of its contents:
{outline}

Code excerpt (may be truncated):
```python
{code_excerpt}
```

Write clear, helpful documentation for this module in Markdown.

Requirements:
- Start with a level-2 heading: "## {short_name} Module"
- Provide a short overview paragraph of what this module does.
- Add a "Key Classes and Functions" section with bullet points.
- Add a "Usage Notes" section if there are any important behaviors or edge cases.
- Do NOT repeat the full code.
- Do NOT include anything unrelated or speculative beyond the outline and excerpt.""")


project_prompt = ChatPromptTemplate.from_template(
"""You are an expert software architect.

You are given a high-level outline of a Python project:

Project outline:
{project_outline}

Project metrics:
{metrics}

UML Class Diagram (Mermaid):
```mermaid
{class_diagram}
```

Write a Markdown documentation page for this project.

Structure it as:

# Project Overview
Short description of what the project does.

# Architecture
How the project is structured (modules, layers, responsibilities).

# Class Diagram
Include the Mermaid diagram in a code block.

# Modules
Brief bullet-point description of the main modules and what they do.

# Data Flow
How data moves between key components (based on the outline).

# Metrics
- Total files: X
- Total classes: X
- Total functions: X
- Total lines of code: X

# Potential Improvements
A few realistic suggestions for improving structure, documentation, or testing.

Base this ONLY on the outline; do not invent technologies that are not mentioned.
Keep it concise, accurate, and helpful to a new developer joining the project.""")


relationship_prompt = ChatPromptTemplate.from_template(
"""You are an expert software architect analyzing code relationships.

Given the following class information, describe the relationship between classes in plain English.

Classes:
{classes_info}

Relationships found:
{relationships}

Write a brief, clear description of:
1. The inheritance hierarchy (if any)
2. The composition relationships (which classes contain instances of other classes)
3. The dependencies (which classes use other classes as parameters or return types)

Keep it factual and based only on the provided information.""")


def generate_function_docstring(code: str) -> str:
    llm = get_llm()
    if llm is None:
        return "Auto-generated docstring (LLM unavailable)"
    chain = function_prompt | llm | StrOutputParser()
    docstring = chain.invoke({"code": code})
    return docstring.strip()


def generate_class_docstring(code: str) -> str:
    llm = get_llm()
    if llm is None:
        return "Auto-generated docstring (LLM unavailable)"
    chain = class_prompt | llm | StrOutputParser()
    docstring = chain.invoke({"code": code})
    return docstring.strip()


def generate_module_markdown(path: str, short_name: str, outline: str, code_excerpt: str) -> str:
    llm = get_llm()
    if llm is None:
        return f"## {short_name} Module\n\n*Documentation generation requires API key.*\n\n{outline}"
    chain = module_prompt | llm | StrOutputParser()
    text = chain.invoke({
        "path": path,
        "short_name": short_name,
        "outline": outline,
        "code_excerpt": code_excerpt,
    })
    return text.strip()


def generate_project_overview_markdown(
    project_outline: str,
    metrics: str = "",
    class_diagram: str = "",
) -> str:
    llm = get_llm()
    if llm is None:
        return f"# Project Overview\n\n*Documentation generation requires API key.*\n\n## Metrics\n{metrics}\n\n## Class Diagram\n```mermaid\n{class_diagram}\n```"
    chain = project_prompt | llm | StrOutputParser()
    text = chain.invoke({
        "project_outline": project_outline,
        "metrics": metrics,
        "class_diagram": class_diagram,
    })
    return text.strip()


def generate_relationship_description(classes_info: str, relationships: str) -> str:
    llm = get_llm()
    if llm is None:
        return f"Relationships:\n{relationships}"
    chain = relationship_prompt | llm | StrOutputParser()
    text = chain.invoke({
        "classes_info": classes_info,
        "relationships": relationships,
    })
    return text.strip()
