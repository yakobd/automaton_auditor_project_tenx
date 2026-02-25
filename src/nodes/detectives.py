from pathlib import Path

from src.state import AgentState, Evidence
from src.tools.doc_tools import analyze_repo_pdf
from src.tools.repo_tools import clone_peer_repo, get_commit_metadata, verify_langgraph_usage


def _evidence(title: str, severity: int, summary: str, source: str) -> Evidence:
	return Evidence(title=title, severity=severity, summary=summary, source=source)


def repo_investigator_node(state: AgentState):
	repo_path = state.get("repo_path")
	repo_url = state.get("repo_url", "")

	if repo_path:
		cloned_path = repo_path
	elif not repo_url:
		error_graph = _evidence(
			"LangGraph Formal Usage",
			5,
			"Repository URL missing from state.",
			"State",
		)
		error_atomic = _evidence(
			"Atomic Progress",
			5,
			"Could not analyze commit history because repository URL is missing.",
			"State",
		)
		return {"evidences": [error_graph, error_atomic], "repo_path": ""}
	else:
		cloned_path = clone_peer_repo(repo_url)

	if isinstance(cloned_path, str) and cloned_path.startswith("Error:"):
		error_graph = _evidence("LangGraph Formal Usage", 5, cloned_path, "Git")
		error_atomic = _evidence(
			"Atomic Progress",
			5,
			"Could not analyze commit history because clone failed.",
			"Git",
		)
		return {"evidences": [error_graph, error_atomic], "repo_path": ""}

	repo_root = Path(cloned_path)
	python_files = list(repo_root.rglob("*.py"))
	has_formal_graph = any(verify_langgraph_usage(str(path)) for path in python_files)

	if has_formal_graph:
		graph_evidence = _evidence(
			"LangGraph Formal Usage",
			1,
			"Detected formal StateGraph(...) assignment in repository source.",
			"AST",
		)
	else:
		graph_evidence = _evidence(
			"LangGraph Formal Usage",
			5,
			"No formal StateGraph(...) assignment detected in scanned Python files.",
			"AST",
		)

	metadata = get_commit_metadata(cloned_path)
	total_commits = int(metadata.get("total_commits", 0))
	last_messages = metadata.get("last_3_commit_messages", [])
	metadata_error = metadata.get("error")

	if metadata_error:
		atomic_evidence = _evidence("Atomic Progress", 5, str(metadata_error), "Git")
	else:
		if total_commits == 0:
			severity = 5
		elif total_commits < 3:
			severity = 3
		else:
			severity = 1
		atomic_evidence = _evidence(
			"Atomic Progress",
			severity,
			f"Total commits: {total_commits}; Recent commits: {last_messages}",
			"Git",
		)

	return {"evidences": [graph_evidence, atomic_evidence], "repo_path": cloned_path}


def doc_analyst_node(state: AgentState):
	repo_path = state.get("repo_path", "")
	if not repo_path:
		error_doc = _evidence(
			"Documentation Coverage",
			5,
			"Repository path missing from state.",
			"State",
		)
		return {"evidences": [error_doc]}

	doc_evidence = analyze_repo_pdf(repo_path)
	return {"evidences": [doc_evidence]}

def judge_node(state: AgentState):
    evidences = state.get("evidences", [])
    score = 100
    
    # Simple Forensic Scoring Logic
    for ev in evidences:
        if ev.severity == 5:
            score -= 30
        elif ev.severity == 3:
            score -= 10
            
    score = max(0, score) # Don't go below 0
    
    status = "PASS" if score >= 70 else "FAIL"
    verdict_text = f"Audit complete. Final Score: {score}/100. Recommendation: {status}."
    
    verdict = Evidence(
        title="Final Audit Verdict",
        severity=1 if score >= 70 else 5,
        summary=verdict_text,
        source="Judge"
    )
    
    return {"evidences": [verdict], "audit_completed": True}