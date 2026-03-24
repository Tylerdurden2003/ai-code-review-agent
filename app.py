from src.agents.critic_agent import critic_agent
from src.agents.architecture_agent import architecture_agent
from src.agents.performance_agent import performance_agent
from src.agents.security_agent import security_agent
from src.ingestion.chunker import chunk_repo
from src.ingestion.parser import get_code_files
from src.ingestion.cloner import clone_repo, cleanup_repo
from src.state import AgentState
from langgraph.graph import StateGraph, END
import streamlit as st
import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🔍",
    layout="wide"
)

MAX_DEBATE_ROUNDS = 2


def filter_important_chunks(chunks, max_chunks=80):
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
    return selected


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
        lambda s: "continue_debate" if s["debate_rounds"] < MAX_DEBATE_ROUNDS else "end",
        {"continue_debate": "critic_agent", "end": END}
    )
    return graph.compile()


def calculate_health_score(findings):
    """
    Lower score = worse health.
    Each severity costs a different number of points.
    """
    score = 100
    weights = {"critical": 20, "high": 10, "medium": 5, "low": 1}
    for f in findings:
        score -= weights.get(f["severity"], 0)
    return max(0, score)


def get_score_color(score):
    if score >= 70:
        return "green"
    elif score >= 40:
        return "orange"
    return "red"


def run_analysis(github_url, max_chunks, progress_container):
    """Runs the full multi-agent analysis and streams progress to the UI."""

    repo_path = None
    try:
        with progress_container:
            st.info("Cloning repository...")
            repo_path = clone_repo(github_url)

            st.info("Parsing code files...")
            code_files = get_code_files(repo_path)
            st.success(f"Found {len(code_files)} code files")

            st.info("Chunking code...")
            chunks = chunk_repo(code_files)
            chunks = filter_important_chunks(chunks, max_chunks)
            st.success(f"Analyzing {len(chunks)} high-priority chunks")

    finally:
        if repo_path:
            cleanup_repo(repo_path)

    st.info("Running multi-agent analysis — this may take a few minutes...")

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
    return final_state


def render_severity_badge(severity):
    colors = {
        "critical": "#E24B4A",
        "high": "#EF9F27",
        "medium": "#378ADD",
        "low": "#639922"
    }
    color = colors.get(severity, "#888")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500">{severity.upper()}</span>'


def render_agent_badge(agent):
    colors = {
        "security": "#993C1D",
        "performance": "#854F0B",
        "architecture": "#534AB7"
    }
    color = colors.get(agent, "#888")
    return f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:11px">{agent.upper()}</span>'

# ── UI STARTS HERE ──


st.title("AI Code Review Agent")
st.caption("Multi-agent system using LangGraph — security, performance, and architecture analysis with critic debate loop")

# Sidebar
with st.sidebar:
    st.header("Configuration")
    github_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/owner/repo",
        help="Enter any public GitHub repository URL"
    )
    max_chunks = st.slider(
        "Chunks to analyze",
        min_value=20,
        max_value=100,
        value=80,
        step=10,
        help="More chunks = more thorough but slower and more tokens"
    )
    st.divider()
    st.caption("Agents")
    st.markdown("🔴 Security — OWASP, injections, secrets")
    st.markdown("🟡 Performance — N+1, complexity, blocking calls")
    st.markdown("🔵 Architecture — SOLID, coupling, god classes")
    st.markdown("⚪ Critic — debate loop, false positive removal")
    st.divider()
    analyze_button = st.button(
        "Analyze Repository", type="primary", use_container_width=True)

# Initialize session state
if "results" not in st.session_state:
    st.session_state.results = None
if "analyzing" not in st.session_state:
    st.session_state.analyzing = False

# Run analysis when button clicked
if analyze_button:
    if not github_url:
        st.error("Please enter a GitHub URL")
    elif not github_url.startswith("https://github.com/"):
        st.error("Please enter a valid GitHub URL starting with https://github.com/")
    else:
        st.session_state.analyzing = True
        st.session_state.results = None
        progress_container = st.container()
        with st.spinner("Running multi-agent analysis..."):
            try:
                final_state = run_analysis(
                    github_url, max_chunks, progress_container)
                st.session_state.results = final_state
                st.session_state.analyzing = False
                st.success("Analysis complete!")
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.session_state.analyzing = False

# Render results
if st.session_state.results:
    final_state = st.session_state.results
    findings = final_state["findings"]
    debate_log = final_state["debate_log"]

    # Health score
    score = calculate_health_score(findings)
    color = get_score_color(score)

    st.divider()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Health Score", f"{score}/100", delta=None)
    with col2:
        critical = len([f for f in findings if f["severity"] == "critical"])
        st.metric("Critical", critical)
    with col3:
        high = len([f for f in findings if f["severity"] == "high"])
        st.metric("High", high)
    with col4:
        medium = len([f for f in findings if f["severity"] == "medium"])
        st.metric("Medium", medium)
    with col5:
        low = len([f for f in findings if f["severity"] == "low"])
        st.metric("Low", low)

    st.divider()

    # Debate summary
    dismissed = len([d for d in debate_log if d["verdict"] == "dismiss"])
    downgraded = len([d for d in debate_log if d["verdict"] == "downgrade"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total findings", len(findings))
    with col2:
        st.metric("Dismissed by critic", dismissed,
                  help="False positives removed")
    with col3:
        st.metric("Downgraded by critic", downgraded,
                  help="Severity reduced after debate")

    st.divider()

    # Filter controls
    st.subheader("Findings")
    col1, col2 = st.columns(2)
    with col1:
        severity_filter = st.multiselect(
            "Filter by severity",
            ["critical", "high", "medium", "low"],
            default=["critical", "high", "medium", "low"]
        )
    with col2:
        agent_filter = st.multiselect(
            "Filter by agent",
            ["security", "performance", "architecture"],
            default=["security", "performance", "architecture"]
        )

    # Apply filters
    filtered = [
        f for f in findings
        if f["severity"] in severity_filter and f["agent"] in agent_filter
    ]

    st.caption(f"Showing {len(filtered)} of {len(findings)} findings")

    # Render findings
    for finding in filtered:
        with st.expander(
            f"[{finding['id']}] {finding['title']} — {finding['file_path'].split(chr(92))[-1]}",
            expanded=finding["severity"] == "critical"
        ):
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(render_severity_badge(
                    finding["severity"]), unsafe_allow_html=True)
                st.markdown(render_agent_badge(
                    finding["agent"]), unsafe_allow_html=True)
            with col2:
                st.markdown(
                    f"**File:** `{finding['file_path']}` lines {finding['start_line']}–{finding['end_line']}")
                st.write(finding["description"])

            if finding.get("patch"):
                st.markdown("**Suggested fix:**")
                st.code(finding["patch"], language="python")

            # Show debate verdict for this finding
            verdicts = [d for d in debate_log if d.get(
                "finding_id") == finding["id"]]
            if verdicts:
                with st.expander("Agent debate", expanded=False):
                    for v in verdicts:
                        verdict_emoji = {"confirm": "✓", "downgrade": "↓", "dismiss": "✗"}.get(
                            v["verdict"], "?")
                        st.markdown(
                            f"**Round {v['round']}** — {verdict_emoji} {v['verdict'].upper()}")
                        st.caption(v.get("reasoning", ""))

else:
    # Empty state
    st.markdown("###")
    st.markdown(
        "Enter a GitHub repository URL in the sidebar and click **Analyze Repository** to start.")
    st.markdown(
        "The system will run 3 specialist agents followed by a critic debate loop to filter false positives.")
