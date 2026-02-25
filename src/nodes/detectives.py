from pathlib import Path
from src.state import AgentState, Evidence, JudicialOpinion
from src.tools.doc_tools import analyze_repo_pdf
from src.tools.repo_tools import clone_peer_repo, get_commit_metadata, verify_langgraph_usage

def _evidence(title: str, severity: int, summary: str, source: str, rationale: str = "", confidence: float = 1.0) -> Evidence:
    """Helper to create Evidence with the new rubric-required fields."""
    return Evidence(
        title=title, 
        severity=severity, 
        summary=summary, 
        source=source,
        rationale=rationale,
        confidence=confidence
    )

def repo_investigator_node(state: AgentState):
    repo_path = state.get("repo_path")
    repo_url = state.get("repo_url", "")

    # 1. ROBUST PATH CHECK
    if repo_path:
        cloned_path = repo_path
    elif not repo_url:
        return {
            "evidences": [
                _evidence("LangGraph Usage", 5, "Missing URL", "State", "Audit blocked: No URL provided in state.", 1.0),
                _evidence("Atomic Progress", 5, "Missing URL", "State", "Cannot analyze history without a target URL.", 1.0)
            ], 
            "repo_path": ""
        }
    else:
        cloned_path = clone_peer_repo(repo_url)

    # 2. ROBUST CLONE ERROR HANDLING
    if isinstance(cloned_path, str) and cloned_path.startswith("Error:"):
        return {
            "evidences": [
                _evidence("LangGraph Usage", 5, "Clone Failed", "Git", f"Sandboxed clone failed: {cloned_path}", 1.0),
                _evidence("Atomic Progress", 5, "Clone Failed", "Git", "History analysis unreachable due to clone failure.", 1.0)
            ], 
            "repo_path": ""
        }

    repo_root = Path(cloned_path)
    
    # --- CHECK A: Repository Hygiene (Large Files) ---
    large_files = [f.name for f in repo_root.rglob("*") if f.is_file() and f.stat().st_size > 5 * 1024 * 1024]
    hygiene_severity = 3 if large_files else 1
    hygiene_summary = f"Detected {len(large_files)} large binaries." if large_files else "No bloated binaries detected."
    hygiene_evidence = _evidence(
        "Repository Hygiene", hygiene_severity, hygiene_summary, "File Scanner",
        "Checks if the repo contains large binaries that violate clean version control practices.", 0.9
    )

    # --- CHECK B: Secret Exposure (Security Check) ---
    forbidden_files = [".env", "secrets.json", "id_rsa"]
    leaked = [f.name for f in repo_root.rglob("*") if f.name in forbidden_files]
    secret_sev = 5 if leaked else 1
    secret_sum = f"DANGER: Leaked secret files: {leaked}" if leaked else "No sensitive secret files detected."
    secret_evidence = _evidence(
        "Secret Exposure", secret_sev, secret_sum, "Security Scanner",
        "Scans for common sensitive files that should not be committed to version control.", 1.0
    )

    # --- CHECK C: AST ANALYSIS (LangGraph) ---
    python_files = list(repo_root.rglob("*.py"))
    has_formal_graph = False
    forensic_errors = []
    
    for path in python_files:
        is_found, message = verify_langgraph_usage(str(path))
        if is_found:
            has_formal_graph = True
            break
        if "Forensic Error" in message:
            forensic_errors.append(message)

    graph_sev = 1 if has_formal_graph else 5
    graph_sum = "StateGraph detected." if has_formal_graph else "No StateGraph found."
    if forensic_errors: graph_sum += f" (Note: {len(forensic_errors)} parse errors)"
    
    graph_evidence = _evidence(
        "LangGraph Usage", graph_sev, graph_sum, "AST",
        "Verifies formal LangGraph construction via Abstract Syntax Tree analysis.", 0.95
    )

    # --- CHECK D: ATOMIC PROGRESS (Git) ---
    metadata = get_commit_metadata(cloned_path)
    total_commits = int(metadata.get("total_commits", 0))
    
    atomic_sev = 1 if total_commits >= 3 else (3 if total_commits > 0 else 5)
    atomic_evidence = _evidence(
        "Atomic Progress", atomic_sev, f"Commits: {total_commits}", "Git",
        "Analyzes commit frequency to ensure incremental development progress.", 1.0
    )

    return {
        "evidences": [graph_evidence, atomic_evidence, hygiene_evidence, secret_evidence], 
        "repo_path": cloned_path
    }

def doc_analyst_node(state: AgentState):
    repo_path = state.get("repo_path", "")
    
    if not repo_path:
        return {"evidences": [_evidence(
            "Documentation Coverage", 5, "Audit Blocked", "System",
            "Docling cannot analyze a non-existent repository path.", 1.0
        )]}

    doc_evidence = analyze_repo_pdf(repo_path)
    
    # Ensure rationale/confidence are present
    if not hasattr(doc_evidence, 'rationale') or not doc_evidence.rationale:
        doc_evidence.rationale = "Evaluated PDF documentation for architectural keywords using RAG-lite chunking."
    if not hasattr(doc_evidence, 'confidence') or not doc_evidence.confidence:
        doc_evidence.confidence = 0.85
    
    return {"evidences": [doc_evidence]}

def judge_node(state: AgentState):
    evidences = state.get("evidences", [])
    score = 100
    
    # Scoring logic: penalize for higher severity
    for ev in evidences:
        if ev.severity == 5: score -= 20
        elif ev.severity == 3: score -= 10
            
    score = max(0, score)
    verdict_val = "PASS" if score >= 70 else "FAIL"
    
    opinion = JudicialOpinion(
        score=score,
        verdict=verdict_val,
        recommendation="Proceed to Phase 2" if verdict_val == "PASS" else "Fix critical audit/security failures.",
        reasoning=f"Final score {score}/100 calculated from {len(evidences)} forensic checks."
    )
    
    return {"opinion": opinion, "audit_completed": True}