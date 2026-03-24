from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from src.state import AgentState
from src.ingestion.cloner import clone_repo, cleanup_repo
from src.ingestion.parser import get_code_files
from src.ingestion.chunker import chunk_repo
from src.agents.security_agent import security_agent
from src.agents.performance_agent import performance_agent
from src.agents.architecture_agent import architecture_agent
from src.agents.critic_agent import critic_agent

load_dotenv()

MAX_DEBATE_ROUNDS = 2


def filter_important_chunks(chunks: list, max_chunks: int = 80) -> list:
    priority_keywords = [
        'auth', 'login', 'password', 'token', 'secret',
        'sql', 'query', 'db', 'database',
        'upload', 'file', 'path',
        'request', 'input', 'form',
        'config', 'setting', 'env'
    ]

    priority_chunks = []
    normal_chunks = []

    for chunk in chunks:
        path_lower = chunk['file_path'].lower()
        if any(kw in path_lower for kw in priority_keywords):
            priority_chunks.append(chunk)
        else:
            normal_chunks.append(chunk)

    selected = priority_chunks[:max_chunks]
    remaining = max_chunks - len(selected)
    if remaining > 0:
        selected += normal_chunks[:remaining]

    print(
        f"Filtered to {len(selected)} high-priority chunks from {len(chunks)} total")
    return selected


def run_ingestion(github_url: str):
    repo_path = None
    try:
        repo_path = clone_repo(github_url)
        code_files = get_code_files(repo_path)
        chunks = chunk_repo(code_files)
        return chunks
    finally:
        if repo_path:
            cleanup_repo(repo_path)


def should_keep_debating(state: AgentState) -> str:
    if state["debate_rounds"] < MAX_DEBATE_ROUNDS:
        return "continue_debate"
    return "end"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("security_agent", security_agent)
    graph.add_node("performance_agent", performance_agent)
    graph.add_node("architecture_agent", architecture_agent)
    graph.add_node("critic_agent", critic_agent)

    graph.set_entry_point("security_agent")

    graph.add_edge("security_agent", "performance_agent")
    graph.add_edge("performance_agent", "architecture_agent")
    graph.add_edge("architecture_agent", "critic_agent")

    graph.add_conditional_edges(
        "critic_agent",
        should_keep_debating,
        {
            "continue_debate": "critic_agent",
            "end": END
        }
    )

    return graph.compile()


def main():
    github_url = "https://github.com/pallets/flask"

    print("=== Phase 1: Ingestion ===")
    chunks = run_ingestion(github_url)

    print("\n=== Filtering chunks ===")
    chunks = filter_important_chunks(chunks, max_chunks=80)

    print("\n=== Phase 2 + 3: Multi-Agent Analysis ===")
    initial_state: AgentState = {
        "repo_url": github_url,
        "chunks": chunks,
        "findings": [],
        "debate_log": [],
        "debate_rounds": 0,
        "current_agent": "security",
        "report": {}
    }

    graph = build_graph()
    final_state = graph.invoke(initial_state)

    print("\n=== Final Results after Debate ===")
    findings = final_state["findings"]
    print(f"Total findings after critic review: {len(findings)}")

    for severity in ["critical", "high", "medium", "low"]:
        sev_findings = [f for f in findings if f["severity"] == severity]
        if sev_findings:
            print(f"\n--- {severity.upper()} ({len(sev_findings)}) ---")
            for f in sev_findings:
                print(f"  [{f['id']}] [{f['agent'].upper()}] {f['title']}")
                print(
                    f"  File: {f['file_path']} lines {f['start_line']}-{f['end_line']}")
                print(f"  {f['description'][:120]}...")

    print(f"\n=== Debate Log ({len(final_state['debate_log'])} verdicts) ===")
    dismissed = [d for d in final_state['debate_log']
                 if d['verdict'] == 'dismiss']
    downgraded = [d for d in final_state['debate_log']
                  if d['verdict'] == 'downgrade']
    print(f"  Dismissed as false positives: {len(dismissed)}")
    print(f"  Downgraded in severity: {len(downgraded)}")


if __name__ == "__main__":
    main()
