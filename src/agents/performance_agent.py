import time
import json
import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, Finding

PERFORMANCE_SYSTEM_PROMPT = """You are an expert performance engineer doing a code review.
Your job is to find performance issues in code chunks.

You look for:
- N+1 query problems (fetching related data in a loop)
- Missing database indexes (filtering/ordering on unindexed columns)
- Inefficient algorithms (O(n²) or worse where better exists)
- Unnecessary repeated computation inside loops
- Large data loaded into memory when streaming would work
- Synchronous blocking calls where async would help

For each issue you find, respond with a JSON array of findings.
Each finding must have exactly these fields:
- severity: "critical", "high", "medium", or "low"
- title: short name of the issue
- description: what the issue is and its performance impact
- patch: a concrete code fix

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


def performance_agent(state: AgentState) -> dict:
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    )

    print(f"\nPerformance agent analyzing {len(state['chunks'])} chunks...")
    all_findings = []

    for i, chunk in enumerate(state['chunks']):
        if i % 20 == 0:
            print(f"  Analyzing chunk {i+1}/{len(state['chunks'])}...")

        prompt = f"""Analyze this code chunk for performance issues.

File: {chunk['file_path']}
Lines: {chunk['start_line']}-{chunk['end_line']}
Language: {chunk['language']}

Code:
{chunk['content']}
"""

        try:
            messages = [
                SystemMessage(content=PERFORMANCE_SYSTEM_PROMPT),
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
                    "id": f"PERF-{len(all_findings)+1:03d}",
                    "severity": f.get("severity", "medium"),
                    "agent": "performance",
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

    print(f"Performance agent found {len(all_findings)} issues")
    return {"findings": all_findings}
