# Automaton Auditor

Automaton Auditor is a LangGraph-based forensic workflow that audits peer repositories for graph construction quality, atomic progress in commit history, and documentation coverage.

## Quick Start

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) installed

### Setup and Run

```bash
uv sync
uv run main.py
```

The startup check confirms environment configuration (without printing secrets), then executes the audit graph.

## Project Structure

```text
src/
├── graph.py                # LangGraph workflow definition (parallel detectives + judge)
├── state.py                # Pydantic Evidence model + AgentState schema/reducers
├── nodes/
│   └── detectives.py       # Graph nodes: repo investigator, doc analyst, judge
└── tools/
	├── repo_tools.py       # Git clone, commit metadata, AST StateGraph verification
	└── doc_tools.py        # PDF/Docling analysis and keyword extraction
```

- `src/tools/` contains reusable forensic utilities (repo analysis + document analysis).
- `src/nodes/` contains orchestration-facing node functions that call tools and emit structured evidence.

## Architecture

The workflow uses a **Diamond Fan-out/Fan-in** pattern:

1. `clone_repo` runs first and prepares a local sandbox path.
2. **Fan-out**: two detectives run in parallel:
   - `repo_investigator` (AST + git history)
   - `doc_analyst` (Docling PDF/document checks)
3. **Fan-in**: both branches merge into `judge`, which aggregates findings and returns a final verdict.

State and evidence handling are strongly typed:

- `Evidence` is a Pydantic model with validated severity (`1..5`).
- `AgentState.evidences` uses `Annotated[list[Evidence], operator.add]` so parallel node outputs are merged by reducer semantics.
- This reducer-based collection ensures forensic evidence from concurrent detectives is accumulated deterministically.

## Notes

- The auditor is designed for interim challenge submissions and incremental hardening.
- Keep secrets in `.env`; never commit real API keys.
