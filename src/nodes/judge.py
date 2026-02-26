import os
import time
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.state import AgentState, Evidence, JudicialOpinion


def _format_judge_evidence(evidences: list[Evidence]) -> str:
    if not evidences:
        return "No evidences were provided."

    rows: list[str] = []
    for index, evidence in enumerate(evidences, start=1):
        rows.append(
            f"{index}. {evidence.title} | severity={evidence.severity} | "
            f"source={evidence.source} | summary={evidence.summary}"
        )
    return "\n".join(rows)


def _format_prosecutor_critique(critique: str) -> str:
    cleaned = (critique or "").strip()
    if not cleaned:
        return "Prosecutor critique unavailable."
    return f"Prosecutor Findings:\n{cleaned}"


def _format_defense_counsel(defense_text: str) -> str:
    cleaned = (defense_text or "").strip()
    if not cleaned:
        return "Defense argument unavailable."
    return f"Defense Argument:\n{cleaned}"


def judge_node(state: AgentState):
    evidences = state.get("evidences", [])
    prosecutor_critique = (state.get("prosecutor_critique") or "").strip()
    defense_counsel = (state.get("defense_counsel") or "").strip()
    score = 100

    for ev in evidences:
        if ev.severity == 5:
            score -= 20
        elif ev.severity == 3:
            score -= 10

    if prosecutor_critique:
        critique_lower = prosecutor_critique.lower()
        if any(keyword in critique_lower for keyword in ["critical", "severe", "high risk", "failed", "block"]):
            score -= 10

    score = max(0, score)
    verdict_val = "PASS" if score >= 70 else "FAIL"

    judge_prompt = (
        "You are the final judicial auditor. Review the structured evidence, the prosecutor critique, and the defense argument. "
        "Explicitly compare prosecutor_critique versus defense_counsel before issuing your verdict. "
        "Do not invent facts. Explain the final verdict clearly and provide strict remediation guidance.\n\n"
        f"Structured Evidence:\n{_format_judge_evidence(evidences)}\n\n"
        f"Prosecutor Critique:\n{prosecutor_critique or 'No prosecutor critique provided.'}\n\n"
        f"Defense Argument:\n{defense_counsel or 'No defense argument provided.'}\n\n"
        f"Computed Final Score: {score}\n"
        f"Computed Verdict: {verdict_val}"
    )

    reasoning_text = f"Final score {score}/100 calculated from {len(evidences)} forensic checks."
    try:
        model = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            groq_api_key=os.getenv('GROQ_API_KEY'),
        )
        time.sleep(2)
        response = model.invoke(
            [
                SystemMessage(content="You are a strict, concise software audit judge."),
                HumanMessage(content=judge_prompt),
            ]
        )
        candidate_reasoning = (response.content or "").strip()
        if candidate_reasoning:
            reasoning_text = candidate_reasoning
    except Exception:
        pass

    return {
        "opinion": JudicialOpinion(
            score=score,
            verdict=verdict_val,
            recommendation="Proceed to Phase 2" if verdict_val == "PASS" else "Fix critical audit/security failures.",
            reasoning=reasoning_text,
        ),
        "prosecutor_critique": _format_prosecutor_critique(prosecutor_critique),
        "defense_counsel": _format_defense_counsel(defense_counsel),
        "audit_completed": True,
    }
