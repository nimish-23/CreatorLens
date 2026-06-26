"""
services/llm_client.py — Lightweight LLM client for non-chain services.
Used by outreach.py for simple chat completions.
"""

import os
import json
import re

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage


def _get_llm():
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.3,
        max_tokens=2048,
    )


async def llm_chat(system_prompt: str, user_message: str) -> str:
    """Simple async chat completion. Returns the response text."""
    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    response = await llm.ainvoke(messages)
    return response.content


def parse_json(raw: str) -> list | dict:
    """Extract JSON from LLM response (handles markdown fences)."""
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = cleaned.strip().rstrip("`")
    return json.loads(cleaned)
