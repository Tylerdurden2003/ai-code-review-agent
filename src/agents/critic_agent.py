import time
import json
import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

CRITIC_SYSTEM_PROMPT = """You are a senior engineering lead reviewing findings from a multi-agent code review.

Your job is to critically evaluate each finding and either:
1. CONFIRM it — the finding is valid and severity is correct
2. DOWNGRADE it — the finding is valid but severity is too high given context
3. DISMISS it — the finding is a false positive or too minor to matter

For each finding you review, respond with a JSON array.
Each item must have exactly these fields:
- finding_id: the id of the finding you are reviewing (e.g. "SEC-001")
- verdict: "confirm", "downgrade", or "dismiss"
- revised_severity: the severity you think it should be (same or lower)
- reasoning: one sentence explaining your verdict

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


def critic_agent(state: AgentState) -> dict:
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY")
    )

    findings = state["findings"]
    debate_round = state["debate_rounds"] + 1
    print(f"\nCritic agent — debate round {debate_round}")
    print(f"  Reviewing {len(findings)} findings...")

    BATCH_SIZE = 10
    all_verdicts = []
    debate_entries = []

    for batch_start in range(0, len(findings), BATCH_SIZE):
        batch = findings[batch_start:batch_start + BATCH_SIZE]

        findings_text = json.dumps([
            {
                "id": f["id"],
                "agent": f["agent"],
                "severity": f["severity"],
                "title": f["title"],
                "description": f["description"],
                "file": f["file_path"]
            }
            for f in batch
        ], indent=2)

        prompt = f"""Review these code review findings and give your verdict on each one.

Round: {debate_round}
Findings to review:
{findings_text}

Remember: be a tough critic. Downgrade or dismiss findings that are:
- Too obvious or low-impact to matter
- False positives given the context (e.g. test files, example code)
- Duplicates of other findings
- Overly severe for what they actually describe
"""

        try:
            messages = [
                SystemMessage(content=CRITIC_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            response = _invoke_with_retry(llm, messages)

            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            verdicts = json.loads(raw)
            all_verdicts.extend(verdicts)

            for verdict in verdicts:
                debate_entries.append({
                    "round": debate_round,
                    "finding_id": verdict.get("finding_id"),
                    "verdict": verdict.get("verdict"),
                    "revised_severity": verdict.get("revised_severity"),
                    "reasoning": verdict.get("reasoning")
                })

        except json.JSONDecodeError:
            continue
        except Exception as e:
            print(f"  Error in critic batch: {e}")
            continue

    verdict_map = {v["finding_id"]: v for v in all_verdicts}
    updated_findings = []
    dismissed = 0
    downgraded = 0
    confirmed = 0

    for finding in findings:
        verdict = verdict_map.get(finding["id"])
        if not verdict:
            updated_findings.append(finding)
            continue

        if verdict["verdict"] == "dismiss":
            dismissed += 1
            continue

        updated = finding.copy()
        if verdict["verdict"] == "downgrade":
            updated["severity"] = verdict.get(
                "revised_severity", finding["severity"])
            downgraded += 1
        else:
            confirmed += 1

        updated_findings.append(updated)

    print(
        f"  Confirmed: {confirmed} | Downgraded: {downgraded} | Dismissed: {dismissed}")
    print(f"  Findings remaining: {len(updated_findings)}")

    return {
        "findings": updated_findings,
        "debate_log": debate_entries,
        "debate_rounds": debate_round
    }
