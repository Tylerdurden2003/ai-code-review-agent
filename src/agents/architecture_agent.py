import time
import json
import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, Finding

ARCHITECTURE_SYSTEM_PROMPT = """You are an expert software architect doing a code review.
Your job is to find architecture and design issues in code chunks.

You look for:
- Single Responsibility violations (class/function doing too many things)
- God classes (one class knowing too much)
- Business logic leaking into wrong layers (e.g. in serializers, views, or models)
- Missing abstraction layers
- Tight coupling between components
- Violation of dependency inversion (high-level depending on low-level)
- Duplicated logic that should be extracted

For each issue you find, respond with a JSON array of findings.
Each finding must have exactly these fields:
- severity: "critical", "high", "medium", or "low"
- title: short name of the issue
- description: what the issue is and why it matters for maintainability
- patch: a concrete refactor suggestion

If you find NO issues in a chunk, return an empty array: []

IMPORTANT: Return ONLY valid JSON. No explanation text before or after.
"""


def _invoke_with_retry(llm, messages):
    try:
        return llm.invoke(messages)
    except Exception as e:
        if "429" in str(e):
            wait_match = re.search(r'try again in (\d+)m', str(e))
            wait_mins = int(wait_match.group(1)) + 1 if wait_match else 2
            print(f"  Rate limit hit — waiting {wait_mins} minutes...")
            time.sleep(wait_mins * 60)
            return llm.invoke(messages)
        raise


def architecture_agent(state: AgentState) -> dict:
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    )

    print(f"\nArchitecture agent analyzing {len(state['chunks'])} chunks...")
    all_findings = []

    for i, chunk in enumerate(state['chunks']):
        if i % 20 == 0:
            print(f"  Analyzing chunk {i+1}/{len(state['chunks'])}...")

        prompt = f"""Analyze this code chunk for architecture and design issues.

File: {chunk['file_path']}
Lines: {chunk['start_line']}-{chunk['end_line']}
Language: {chunk['language']}

Code:
{chunk['content']}
"""

        try:
            messages = [
                SystemMessage(content=ARCHITECTURE_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            response = _invoke_with_retry(llm, messages)

            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            findings = json.loads(raw)

            for f in findings:
                finding: Finding = {
                    "id": f"ARCH-{len(all_findings)+1:03d}",
                    "severity": f.get("severity", "medium"),
                    "agent": "architecture",
                    "title": f.get("title", "Unknown"),
                    "description": f.get("description", ""),
                    "file_path": chunk["file_path"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "patch": f.get("patch", "")
                }
                all_findings.append(finding)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"  Error on chunk {i}: {e}")
            continue

    print(f"Architecture agent found {len(all_findings)} issues")
    return {"findings": all_findings}
