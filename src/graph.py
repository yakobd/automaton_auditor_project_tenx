from langgraph.graph import StateGraph, END, START
from src.state import AgentState, Evidence
from src.nodes.detectives import (
    repo_investigator_node, 
    doc_analyst_node,
)
from src.nodes.judge import judge_node
from src.nodes.defense import defense_node
from src.nodes.prosecutor import prosecutor_node
from src.nodes.tech_lead import tech_lead_node
from src.nodes.justice import justice_node
from src.tools.repo_tools import clone_peer_repo

# 1. CLONE NODE
def clone_repo_node(state: AgentState):
    repo_url = state.get("repo_url", "")
    if not repo_url:
        return {
            "repo_path": "",
            "evidences": [
                Evidence(
                    title="Repository Clone",
                    severity=5,
                    summary="Clone failed: missing repository URL.",
                    source="Clone Node",
                    rationale="No repo_url was provided in AgentState, so the audit cannot start.",
                    confidence=1.0,
                ),
                Evidence(
                    title="Audit Execution",
                    severity=5,
                    summary="Parallel analysis skipped due to clone failure.",
                    source="Router",
                    rationale="Without a valid clone path, detective nodes are bypassed and routed directly to judge.",
                    confidence=1.0,
                ),
            ],
        }
    path = clone_peer_repo(repo_url)
    if not path or (isinstance(path, str) and "Error" in path):
        return {
            "repo_path": path or "",
            "evidences": [
                Evidence(
                    title="Repository Clone",
                    severity=5,
                    summary=f"Clone failed: {path or 'Unknown clone error'}",
                    source="Clone Node",
                    rationale="The repository could not be cloned into the forensic sandbox.",
                    confidence=1.0,
                ),
                Evidence(
                    title="Audit Execution",
                    severity=5,
                    summary="Parallel analysis skipped due to clone failure.",
                    source="Router",
                    rationale="Without a valid clone path, detective nodes are bypassed and routed directly to judge.",
                    confidence=1.0,
                ),
            ],
        }
    return {"repo_path": path}

def route_after_clone(state: AgentState):
    path = state.get("repo_path")
    if not path or (isinstance(path, str) and "Error" in path):
        return "failed"
    return "success"

def build_graph():
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("clone_repo", clone_repo_node)
    workflow.add_node("repo_investigator", repo_investigator_node)
    workflow.add_node("doc_analyst", doc_analyst_node)
    workflow.add_node("prosecutor", prosecutor_node)
    workflow.add_node("defense", defense_node)
    workflow.add_node("tech_lead", tech_lead_node)
    workflow.add_node("judge", judge_node)
    workflow.add_node("justice", justice_node)

    # --- THE ARCHITECTURE ---
    workflow.add_edge(START, "clone_repo")

    # FIXED CONDITIONAL: Points to single strings only!
    workflow.add_conditional_edges(
        "clone_repo",
        route_after_clone,
        {
            "success": "repo_investigator",
            "failed": "repo_investigator",
        }
    )

    # Sequential flow to reduce API burst pressure
    workflow.add_edge("repo_investigator", "doc_analyst")
    workflow.add_edge("doc_analyst", "prosecutor")
    workflow.add_edge("prosecutor", "defense")
    workflow.add_edge("defense", "tech_lead")
    workflow.add_edge("tech_lead", "judge")
    workflow.add_edge("judge", "justice")

    workflow.add_edge("justice", END)

    return workflow.compile()

graph = build_graph()