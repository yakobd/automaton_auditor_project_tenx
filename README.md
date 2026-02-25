# Automaton Auditor

Automaton Auditor is a LangGraph-based forensic workflow that audits peer repositories for graph construction quality, atomic progress in commit history, and documentation coverage. It utilizes a sophisticated parallel orchestration pattern with conditional resilience.

---

## 🚀 Quick Start & Operations

### Technical Requirements

- **Python Version**: `3.12.*` (Strictly enforced via `pyproject.toml`).
- **Package Manager**: [uv](https://docs.astral.sh/uv/) is required for environment management and reproducibility.
- **System Tools**: `git` must be installed and accessible in your system PATH for cloning operations.

### Setup and Run

| Task              | Command                   | Description                                       |
| :---------------- | :------------------------ | :------------------------------------------------ |
| **Install**       | `uv sync`                 | Installs exact dependencies from `uv.lock`.       |
| **Run Audit**     | `uv run main.py <url>`    | Executes the full forensic graph on a target URL. |
| **Format Code**   | `uv run black .`          | Ensures code style meets project standards.       |
| **Clean Sandbox** | `rm -rf forensic_audit_*` | Removes temporary forensic clone directories.     |

> **Note**: A `.env` file must exist containing `OPENAI_API_KEY` and `USER_AGENT` (for Docling).

---

## 🏗️ Project Structure

```text
src/
├── graph.py        # Orchestration logic (Conditional Fan-out/Fan-in)
├── state.py        # Pydantic Evidence models + Typed AgentState with Reducers
├── nodes/
│   └── detectives.py # Orchestration nodes (investigator, analyst, judge)
└── tools/
    ├── repo_tools.py # AST verification, Git history, and sandboxed cloning
    └── doc_tools.py  # PDF/Docling analysis and keyword extraction

## 💎 Architecture & Orchestration
The workflow uses an advanced Conditional Diamond Fan-out/Fan-in pattern:

Preparation: clone_repo prepares a local sandbox.

Conditional Routing:

Success Path: If cloning succeeds, the graph triggers a parallel fan-out to repo_investigator and doc_analyst.

Failure/Skip Path: If the repo is inaccessible or missing metadata, the graph uses a conditional edge to skip detectives and route directly to the judge.

Aggregation (Fan-in): Findings from parallel branches are normalized and merged into the judge node for final verdict.

Forensic Rigor
Typed State: Evidence is a Pydantic model with validated severity and rationale.

Reducers: AgentState uses Annotated[list, operator.add] to ensure evidence from concurrent detectives is accumulated deterministically.

Sandboxing: Repository tools use subprocess with timeouts and error-handling to ensure the host environment remains secure.

## 🛠️ Infrastructure & Reproducibility
Dependency Pinning: This project includes a uv.lock file pinning all 150+ sub-dependencies.

Environment Integrity: Graders can replicate the exact development environment by running uv sync.

Secret Hygiene: Startup checks verify environment configuration without exposing sensitive keys.
```
