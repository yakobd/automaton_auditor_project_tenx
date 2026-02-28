import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.state import AgentState, Evidence, JudicialOpinion


def test_agent_state_accepts_new_opinion_and_evidence() -> None:
    state = AgentState(repo_url="https://github.com/example/repo.git")

    new_opinion = JudicialOpinion(
        judge="Prosecutor",
        criterion_id="safe_tool_engineering",
        score=4,
        argument="Tooling uses subprocess with strict options.",
        cited_evidence=["src/tools/repo_tools.py"],
    )
    state.opinions.append(new_opinion)

    new_evidence = Evidence(
        goal="Repository clone operation succeeds",
        found=True,
        content="clone command executed with subprocess.run",
        location="src/tools/repo_tools.py",
        rationale="Command uses shell=False and check=True.",
        confidence=0.95,
    )
    state.evidences.setdefault("safe_tool_engineering", []).append(new_evidence)

    assert len(state.opinions) == 1
    assert state.opinions[0].judge == "Prosecutor"
    assert state.opinions[0].criterion_id == "safe_tool_engineering"

    assert "safe_tool_engineering" in state.evidences
    assert len(state.evidences["safe_tool_engineering"]) == 1
    assert state.evidences["safe_tool_engineering"][0].found is True
    assert state.evidences["safe_tool_engineering"][0].confidence == 0.95
