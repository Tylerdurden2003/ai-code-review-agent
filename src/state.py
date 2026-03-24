from typing import TypedDict, List, Annotated
import operator


class Finding(TypedDict):
    id: str
    severity: str        # "critical", "high", "medium", "low"
    agent: str           # which agent found it
    title: str
    description: str
    file_path: str
    start_line: int
    end_line: int
    patch: str           # suggested fix


class AgentState(TypedDict):
    repo_url: str
    chunks: List[dict]
    findings: Annotated[List[Finding], operator.add]  # agents append to this
    debate_log: Annotated[List[dict], operator.add]
    debate_rounds: int
    current_agent: str
    report: dict
