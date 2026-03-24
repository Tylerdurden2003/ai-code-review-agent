# AI Code Review Agent

> Multi-agent LLM system that autonomously analyzes GitHub repositories for security, performance, and architecture issues — with a critic debate loop that filters false positives.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red)
![Groq](https://img.shields.io/badge/Groq-API-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

## What it does

Give it any public GitHub repository URL. Three specialist AI agents independently analyze the codebase across security, performance, and architecture dimensions. A critic agent then runs a 2-round debate loop — dismissing false positives and downgrading overly severe findings — before generating a structured report with AI-suggested patches.

**On the Flask repository (83 files, 569 chunks):**

- Found 832 total findings across 3 agents
- Critic dismissed 483 false positives (48% reduction)
- Critic downgraded 134 severity ratings
- Final report: actionable, high-confidence findings only

## Architecture

```
GitHub URL
    │
    ▼
Ingestion Pipeline
(clone → parse → chunk → prioritize)
    │
    ├──► Security Agent ──┐
    ├──► Performance Agent ──┼──► Critic Debate Loop (2 rounds) ──► Final Report
    └──► Architecture Agent ─┘
```

### Agent roles

| Agent        | Finds                                                                      | Model                |
| ------------ | -------------------------------------------------------------------------- | -------------------- |
| Security     | SQL injection, hardcoded secrets, path traversal, insecure deserialization | llama-3.1-8b-instant |
| Performance  | N+1 queries, blocking calls, inefficient algorithms, missing indexes       | llama-3.1-8b-instant |
| Architecture | SOLID violations, god classes, tight coupling, business logic leaks        | llama-3.1-8b-instant |
| Critic       | Reviews all findings, dismisses false positives, downgrades severity       | llama-3.1-8b-instant |

### Key technical decisions

- **LangGraph state graph** with `Annotated` reducer functions merge findings from all agents without data loss
- **Conditional edges** control the debate loop — exits after 2 rounds or when findings stabilize
- **Smart chunk prioritization** filters 500+ files to 80 high-risk chunks using keyword triage, cutting token usage by 85%
- **Rate limit self-healing** — agents auto-retry with exponential backoff on API limits
- **Structured JSON outputs** from every agent enable consistent parsing and report generation

## Tech stack

- **Agent framework** — LangGraph, LangChain
- **LLM** — Groq API (llama-3.1-8b-instant)
- **Code parsing** — gitpython, custom AST-aware chunker
- **Frontend** — Streamlit
- **Language** — Python 3.11

## Setup

**1. Clone and install**

```bash
git clone https://github.com/Tylerdurden2003/ai-code-review-agent.git
cd ai-code-review-agent
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

**2. Get a free Groq API key**

Go to [console.groq.com](https://console.groq.com) → API Keys → Create key (free, no credit card)

**3. Create `.env` file**

```
GROQ_API_KEY=your_key_here
```

**4. Run**

```bash
streamlit run app.py
```

Open `http://localhost:8501`, enter any public GitHub URL, and click Analyze.

## Project structure

```
ai-code-review-agent/
├── app.py                    # Streamlit UI
├── main.py                   # CLI entry point
├── src/
│   ├── state.py              # LangGraph shared state definition
│   ├── agents/
│   │   ├── security_agent.py
│   │   ├── performance_agent.py
│   │   ├── architecture_agent.py
│   │   └── critic_agent.py
│   └── ingestion/
│       ├── cloner.py         # Git repo cloning
│       ├── parser.py         # File filtering and reading
│       └── chunker.py        # Overlap-aware code chunking
└── requirements.txt
```

## Why the debate loop?

A single LLM agent analyzing code produces noisy results — it flags test files, example code, and well-known patterns as vulnerabilities. The critic agent debate loop, inspired by [multi-agent debate research from MIT and Google](https://arxiv.org/abs/2305.14325), solves this by having a senior-engineer-persona LLM critically review every finding and either confirm, downgrade, or dismiss it. On the Flask codebase, this removed 48% of findings as false positives.

## Future improvements

- Parallel agent execution using LangGraph fan-out (3x speed improvement)
- Downloadable `.diff` patch files for one-click fixes
- RAGAS evaluation metrics for finding quality measurement
- Support for private repositories via GitHub token auth
- Persistent result storage across sessions

## Author

**Abhinav Gopal P** — [GitHub](https://github.com/Tylerdurden2003) · [LinkedIn](https://linkedin.com/in/abhinav-gopal-1aa9792b4)
