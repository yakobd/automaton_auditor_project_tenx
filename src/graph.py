from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import END, START, StateGraph
from src.nodes.detectives import doc_analyst_node, repo_investigator_node, judge_node
from src.state import AgentState
from src.tools.repo_tools import clone_peer_repo

def clone_repo_node(state: AgentState):
    repo_url = state.get("repo_url", "")
    if not repo_url:
        return {"repo_path": None}

    repo_path = clone_peer_repo(repo_url)
    if isinstance(repo_path, str) and repo_path.startswith("Error:"):
        return {"repo_path": None}

    return {"repo_path": repo_path}

# 1. Initialize the Graph
builder = StateGraph(AgentState)

# 2. Add all three nodes
builder.add_node("clone_repo", clone_repo_node)
builder.add_node("repo_investigator", repo_investigator_node)
builder.add_node("doc_analyst", doc_analyst_node)
builder.add_node("judge", judge_node)

# 3. Define the Flow
builder.add_edge(START, "clone_repo")

# FAN-OUT: Start both detectives at the same time after cloning
builder.add_edge("clone_repo", "repo_investigator")
builder.add_edge("clone_repo", "doc_analyst")

# FAN-IN: Both detectives must finish before the judge runs
builder.add_edge("repo_investigator", "judge")
builder.add_edge("doc_analyst", "judge")

# 4. Finish
builder.add_edge("judge", END)

graph = builder.compile()
