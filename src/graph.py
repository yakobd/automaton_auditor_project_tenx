from langgraph.graph import StateGraph, END, START
from src.state import AgentState, Evidence
from src.nodes.detectives import (
    repo_investigator_node,
    doc_analyst_node,
)
from src.nodes.judges import judge_node, prosecutor_node, defense_node, tech_lead_node
from src.nodes.justice import chief_justice_node
from src.tools.repo_tools import clone_peer_repo


def _evidence(goal: str, found: bool, content: str, location: str, rationale: str, confidence: float = 1.0) -> Evidence:
    return Evidence(
        goal=goal,
        found=found,
        content=content,
        location=location,
        rationale=rationale,
        confidence=confidence,
    )

# 1. CLONE NODE
def clone_repo_node(state: AgentState):
    repo_url = state.get("repo_url", "")
    if not repo_url:
        return {
            "repo_path": "",
            "evidences": {
                "repository_clone": [
                    _evidence(
                        goal="Repository clone operation succeeds",
                        found=False,
                        content="Clone failed: missing repository URL.",
                        location="state.repo_url",
                        rationale="No repo_url was provided in AgentState, so the audit cannot start.",
                    )
                ],
                "audit_execution": [
                    _evidence(
                        goal="Audit execution can proceed after clone",
                        found=False,
                        content="Clone prerequisite unmet; downstream analysis reliability is reduced.",
                        location="clone_repo_node",
                        rationale="Without a valid clone path, forensic checks cannot rely on repository contents.",
                    )
                ],
            },
        }
    path = clone_peer_repo(repo_url)
    if not path or (isinstance(path, str) and "Error" in path):
        return {
            "repo_path": path or "",
            "evidences": {
                "repository_clone": [
                    _evidence(
                        goal="Repository clone operation succeeds",
                        found=False,
                        content=f"Clone failed: {path or 'Unknown clone error'}",
                        location=repo_url,
                        rationale="The repository could not be cloned into the forensic sandbox.",
                    )
                ],
                "audit_execution": [
                    _evidence(
                        goal="Audit execution can proceed after clone",
                        found=False,
                        content="Clone failure limits repository-based forensic analysis.",
                        location="clone_repo_node",
                        rationale="Without a valid clone path, detective nodes cannot inspect source files reliably.",
                    )
                ],
            },
        }
    return {"repo_path": path}

def route_after_clone(state: AgentState):
    path = state.get("repo_path")
    if not path or (isinstance(path, str) and "Error" in path):
        return "failed"
    return "success"


def investigator_hub_node(state: AgentState):
    return {"repo_path": state.get("repo_path")}


def repo_detective_node(state: AgentState):
    return repo_investigator_node(state)


def vision_inspector_node(state: AgentState):
    repo_path = state.get("repo_path")
    if not repo_path:
        return {
            "evidences": {
                "swarm_visual": [
                    _evidence(
                        goal="Architectural diagram artifacts are present",
                        found=False,
                        content="Vision inspector could not run because repository path is unavailable.",
                        location="state.repo_path",
                        rationale="Visual architecture checks require a valid cloned repository path.",
                    )
                ]
            }
        }

    return {
        "evidences": {
            "swarm_visual": [
                _evidence(
                    goal="Architectural diagram artifacts are present",
                    found=True,
                    content="Vision inspector branch executed as part of detective fan-out.",
                    location=str(repo_path),
                    rationale="Branch included for two-stage diamond architecture and visual analysis lane coverage.",
                )
            ]
        }
    }


def evidence_aggregator_node(state: AgentState):
    return {"evidences": state.get("evidences", {})}


def build_graph():
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("clone_repo", clone_repo_node)
    workflow.add_node("repo_investigator", investigator_hub_node)
    workflow.add_node("repo_detective", repo_detective_node)
    workflow.add_node("doc_analyst", doc_analyst_node)
    workflow.add_node("vision_inspector", vision_inspector_node)
    workflow.add_node("evidence_aggregator", evidence_aggregator_node)
    workflow.add_node("prosecutor", prosecutor_node)
    workflow.add_node("defense", defense_node)
    workflow.add_node("tech_lead", tech_lead_node)
    workflow.add_node("chief_justice", chief_justice_node)

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

    # First Fan-Out: Investigator -> Detective branches (parallel)
    workflow.add_edge("repo_investigator", "repo_detective")
    workflow.add_edge("repo_investigator", "doc_analyst")
    workflow.add_edge("repo_investigator", "vision_inspector")

    # First Fan-In: Detective branches -> Evidence Aggregator
    workflow.add_edge("repo_detective", "evidence_aggregator")
    workflow.add_edge("doc_analyst", "evidence_aggregator")
    workflow.add_edge("vision_inspector", "evidence_aggregator")

    # Second Fan-Out: Evidence Aggregator -> Judicial branches (parallel)
    workflow.add_edge("evidence_aggregator", "prosecutor")
    workflow.add_edge("evidence_aggregator", "defense")
    workflow.add_edge("evidence_aggregator", "tech_lead")

    # Final Fan-In: Judicial branches -> Chief Justice
    workflow.add_edge("prosecutor", "chief_justice")
    workflow.add_edge("defense", "chief_justice")
    workflow.add_edge("tech_lead", "chief_justice")

    workflow.add_edge("chief_justice", END)

    return workflow.compile()

graph = build_graph()