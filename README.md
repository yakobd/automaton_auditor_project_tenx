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

🛠️ Infrastructure & Troubleshooting (Add to README)
🛡️ Dependency Pinning & Reproducibility

Lock File: A uv.lock file is included in this repository to ensure 100% reproducible builds across different environments.


Environment Integrity: Running uv sync installs the exact 157 sub-dependencies used during development, eliminating "version drift" issues common with standard requirements.txt files.

🔍 Expected Outputs
When running the audit (uv run main.py <url>), you should expect the following sequence:


Environment Check: Confirms LANGCHAIN_API_KEY presence.


Node Tracing: Real-time console logs showing node entry/exit (e.g., [Node Completed]: repo_investigator).


Final Report: A structured summary of Evidence objects with Severity and Rationale.

Issue,Cause,Solution
Authentication Error,Missing or invalid API Key,Ensure OPENAI_API_KEY is set in your .env file.
Clone Failure,Private repo or invalid URL,The graph will trigger a Conditional Failure Path and route directly to the Judge for a graceful report.+1
ModuleNotFoundError,Out-of-sync environment,Run uv sync to refresh the virtual environment from the lock file.
Docling Timeout,Massive PDF files,Docling may take 30-60s for large documents; do not interrupt the process.
```
