import time
import json
import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, Finding

SECURITY_SYSTEM_PROMPT = """You are an expert security engineer doing a code review.
Your job is to find security vulnerabilities in code chunks.

You look for:
- SQL injection (raw string queries with user input)
- Hardcoded secrets (API keys, passwords in code)
- Insecure deserialization
- Path traversal vulnerabilities
- Unvalidated user input being used dangerously
- Insecure direct object references

For each vulnerability you find, respond with a JSON array of findings.
Each finding must have exactly these fields:
- severity: "critical", "high", "medium", or "low"
- title: short name of the vulnerability
- description: what the vulnerability is and why it's dangerous
- patch: a concrete code fix

If you find NO vulnerabilities in a chunk, return an empty array: []

IMPORTANT: Return ONLY valid JSON. No explanation text before or after.
"""


def security_agent(state: AgentState) -> dict:
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    )

    print(f"\nSecurity agent analyzing {len(state['chunks'])} chunks...")
    all_findings = []

    for i, chunk in enumerate(state['chunks']):
        if i % 20 == 0:
            print(f"  Analyzing chunk {i+1}/{len(state['chunks'])}...")

        prompt = f"""Analyze this code chunk for security vulnerabilities.

File: {chunk['file_path']}
Lines: {chunk['start_line']}-{chunk['end_line']}
Language: {chunk['language']}

Code:
{chunk['content']}
"""

        try:
            response = llm.invoke([
                SystemMessage(content=SECURITY_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])

            raw = response.content.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            findings = json.loads(raw)

            for f in findings:
                finding: Finding = {
                    "id": f"SEC-{len(all_findings)+1:03d}",
                    "severity": f.get("severity", "medium"),
                    "agent": "security",
                    "title": f.get("title", "Unknown"),
                    "description": f.get("description", ""),
                    "file_path": chunk["file_path"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"],
                    "patch": f.get("patch", "")
                }
                all_findings.append(finding)

        except Exception as e:
            if "429" in str(e):
                wait_match = re.search(r'try again in (\d+)m', str(e))
                wait_mins = int(wait_match.group(1)) + 1 if wait_match else 2
                print(f"  Rate limit hit — waiting {wait_mins} minutes...")
                time.sleep(wait_mins * 60)
                try:
                    response = llm.invoke([
                        SystemMessage(content=SECURITY_SYSTEM_PROMPT),
                        HumanMessage(content=prompt)
                    ])
                    raw = response.content.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    findings = json.loads(raw)
                    for f in findings:
                        finding: Finding = {
                            "id": f"SEC-{len(all_findings)+1:03d}",
                            "severity": f.get("severity", "medium"),
                            "agent": "security",
                            "title": f.get("title", "Unknown"),
                            "description": f.get("description", ""),
                            "file_path": chunk["file_path"],
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "patch": f.get("patch", "")
                        }
                        all_findings.append(finding)
                except Exception as retry_error:
                    print(f"  Retry failed on chunk {i}: {retry_error}")
                    continue
            elif "JSONDecodeError" in type(e).__name__ or isinstance(e, json.JSONDecodeError):
                continue
            else:
                print(f"  Error on chunk {i}: {e}")
                continue

    print(f"Security agent found {len(all_findings)} issues")
    return {"findings": all_findings}
