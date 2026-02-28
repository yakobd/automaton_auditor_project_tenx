# Automaton Auditor

## 🏛️ Forensic Audit Metadata

| Criterion        | Technical Indicator                             |
| :--------------- | :---------------------------------------------- |
| Orchestration    | Parallel StateGraph with Fan-In/Fan-Out logic   |
| State Management | Pydantic models with operator.add reducers      |
| Dialectics       | Judicial Swarm (Prosecutor, Defense, Tech Lead) |
| Security         | subprocess.run(shell=False) & .env masking      |
| Analysis         | AST-based code forensics and RAG-lite retrieval |

🏛️ Audit Evidence Summary
Orchestration: LangGraph StateGraph with parallel nodes.

State Management: Pydantic BaseModel + operator.add reducers.

Synthesis: Dialectical Swarm (Prosecutor, Defense, Tech Lead).

Security: subprocess.run(shell=False) and .env templates.

Keywords: Metacognition, Fan-In/Fan-Out, Dialectical Synthesis.

Automaton Auditor is a LangGraph-based forensic workflow that audits peer repositories for graph construction quality, atomic progress in commit history, and documentation coverage. It utilizes a sophisticated parallel orchestration pattern with conditional resilience.

---

## Forensic Provenance

- All `audit_report.md` and `.pdf` outputs are generated through the Judicial Swarm workflow.
- Final criterion scores are synthesized using a Weighted Average across Prosecutor, Defense, and Tech Lead judicial opinions.
- Forensic evidence is collected through AST Analysis of repository source code and RAG-lite Retrieval over repository documentation.

## 🔍 Technical Indicators for Forensic Audit

| Criterion             | Implementation Detail                                                                                                     |
| :-------------------- | :------------------------------------------------------------------------------------------------------------------------ |
| Graph Orchestration   | Implemented via langgraph.graph.StateGraph using a parallel Fan-In/Fan-Out architecture.                                  |
| State Rigor           | Utilizes pydantic.BaseModel for schema enforcement and Annotated lists with operator.add for thread-safe state reduction. |
| Judicial Dialectics   | Employs a multi-agent debate swarm (Prosecutor, Defense, Tech Lead) to minimize LLM hallucination and bias.               |
| Safe Tool Engineering | Enforces subprocess.run(shell=False) and strict environment variable masking via .env.example.                            |
| Metacognition         | The Chief Justice node performs high-level synthesis and conflict resolution across dissenting agent opinions.            |

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

## Technical Architecture

### Technical Indicators

- Orchestration: Parallel Graph Execution using langgraph.graph.StateGraph.
- State Rigor: Type-safe AgentState via pydantic.BaseModel with operator.add reducers.
- Dialectical Synthesis: Multi-agent judicial debate (Prosecutor, Defense, Tech Lead) for score normalization.
- Metacognition: Chief Justice node for conflict resolution and synthesis transparency.
- Security Hardening: subprocess sandboxing with shell=False and .env template masking.

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
