from langgraph.graph import StateGraph, END, START
from src.state import AgentState
from src.nodes.detectives import (
    repo_investigator_node, 
    doc_analyst_node, 
    judge_node
)
from src.tools.repo_tools import clone_peer_repo

# 1. CLONE NODE (The common ancestor for parallel fan-out)
def clone_repo_node(state: AgentState):
    repo_url = state.get("repo_url", "")
    if not repo_url:
        return {"repo_path": "Error: No URL provided"}
    
    path = clone_peer_repo(repo_url)
    return {"repo_path": path}

# 2. ROUTING LOGIC (The intelligence)
def route_after_clone(state: AgentState):
    path = state.get("repo_path")
    if not path or (isinstance(path, str) and path.startswith("Error:")):
        # If clone fails, skip detectives and go straight to judge
        return "failed"
    # Otherwise, run detectives in parallel
    return "success"

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("clone_repo", clone_repo_node)
    workflow.add_node("repo_investigator", repo_investigator_node)
    workflow.add_node("doc_analyst", doc_analyst_node)
    workflow.add_node("judge", judge_node)

    # --- THE ARCHITECTURE ---
    
    # START -> Clone
    workflow.add_edge(START, "clone_repo")

    # CONDITIONAL FAN-OUT
    workflow.add_conditional_edges(
        "clone_repo",
        route_after_clone,
        {
            "success": ["repo_investigator", "doc_analyst"], # PARALLEL BRANCHES
            "failed": "judge"                                # FAILURE PATH
        }
    )

    # FAN-IN (Aggregation)
    # Both parallel branches merge here automatically
    workflow.add_edge("repo_investigator", "judge")
    workflow.add_edge("doc_analyst", "judge")

    workflow.add_edge("judge", END)

    return workflow.compile()

graph = build_graph()