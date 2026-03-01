from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
# Load environment variables from .env
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("GOOGLE_API_KEY is not set in environment or .env file.")

# IMPORTANT: langchain_google_genai reads GOOGLE_API_KEY from env automatically,
# so we don't need to pass it explicitly.
# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-pro",  # or "gemini-1.5-flash" for cheaper/faster
#     temperature=0.1,
# )


# Create a ChatGroq model (using llama-3.3-70b-versatile)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)


function_prompt = ChatPromptTemplate.from_template(
    """
You are an expert Python developer.

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
""")
function_chain = function_prompt | llm | StrOutputParser()
class_prompt = ChatPromptTemplate.from_template(
"""
You are an expert Python developer.

Write a concise, accurate docstring for the following Python class.

Requirements:

Google-style docstring.

Describe the purpose of the class, its main responsibilities, and important attributes or methods.

Be strictly consistent with the code (no hallucinations).

DO NOT include the class signature.

DO NOT wrap the docstring in quotes. Return ONLY the inner text.

Code:
{code}
"""
)
class_chain = class_prompt | llm | StrOutputParser()
# Module Level Documentation (NEW)
module_prompt = ChatPromptTemplate.from_template(
"""
You are an expert software engineer and technical writer.

You are given information about a single Python module.

File path:
{path}

High-level outline of its contents:
{outline}

Code excerpt (may be truncated):
{code_excerpt}
Write clear, helpful documentation for this module in Markdown.

Requirements:

Start with a level-2 heading: "## {short_name} Module"

Provide a short overview paragraph of what this module does.

Add a "Key Classes and Functions" section with bullet points.

Add a "Usage Notes" section if there are any important behaviors or edge cases.

Do NOT repeat the full code.

Do NOT include anything unrelated or speculative beyond the outline and excerpt.
"""
)

module_chain = module_prompt | llm | StrOutputParser()
# Project-level overview (Markdown)


project_prompt = ChatPromptTemplate.from_template(
"""
You are an expert software architect.

You are given a high-level outline of a Python project:

Project outline:
{project_outline}

Write a Markdown documentation page for this project.

Structure it as:

Project Overview

Short description of what the project does.

Architecture

How the project is structured (modules, layers, responsibilities).

Modules

Brief bullet-point description of the main modules and what they do.

Data Flow (if applicable)

How data moves between key components (based on the outline).

Potential Improvements

A few realistic suggestions for improving structure, documentation, or testing.

Base this ONLY on the outline; do not invent technologies that are not mentioned.

Keep it concise, accurate, and helpful to a new developer joining the project.
"""
)

project_chain = project_prompt | llm | StrOutputParser()


def generate_function_docstring(code: str) -> str:
    """Generate a docstring for a standalone function or a method."""
    docstring = function_chain.invoke({"code": code})
    return docstring.strip()

def generate_class_docstring(code: str) -> str:
    """Generate a docstring for a class."""
    docstring = class_chain.invoke({"code": code})
    return docstring.strip()

def generate_module_markdown(path: str, short_name: str, outline: str, code_excerpt: str) -> str:
    """Generate Markdown documentation for a single module/file."""
    text = module_chain.invoke(
    {
    "path": path,
    "short_name": short_name,
    "outline": outline,
    "code_excerpt": code_excerpt,
    }
    )
    return text.strip()

def generate_project_overview_markdown(project_outline: str) -> str:
    text = project_chain.invoke({"project_outline": project_outline})
    return text.strip()
