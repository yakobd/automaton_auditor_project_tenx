import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.state import AgentState, JudicialOpinion


def _format_evidence_block(state: AgentState) -> str:
    evidence_map = state.get("evidences", {})
    if not evidence_map:
        return "No evidences were provided."

    lines: list[str] = []
    item_index = 1
    for dimension, evidences in evidence_map.items():
        for evidence in evidences:
            goal = getattr(evidence, "goal", "Unknown goal")
            found = getattr(evidence, "found", False)
            content = getattr(evidence, "content", "")
            location = getattr(evidence, "location", "Unknown")
            lines.append(
                f"{item_index}. Dimension: {dimension} | goal={goal} | found={found} | location={location} | content={content or 'N/A'}"
            )
            item_index += 1

    if not lines:
        return "No evidences were provided."

    return "\n".join(lines)


def _resolve_criterion_ids(state: AgentState) -> list[str]:
    ids: list[str] = []
    for dimension in state.get("rubric_dimensions", []):
        if not isinstance(dimension, dict):
            continue
        criterion_id = str(dimension.get("id") or dimension.get("dimension_id") or "").strip()
        if criterion_id and criterion_id not in ids:
            ids.append(criterion_id)
    return ids or ["general"]


def _build_binding_law(state: AgentState, criterion_id: str) -> str:
    dimension_payload: dict = {}
    for dimension in state.get("rubric_dimensions", []):
        if isinstance(dimension, dict) and str(dimension.get("id") or "") == criterion_id:
            dimension_payload = dimension
            break

    judicial_logic = str(dimension_payload.get("judicial_logic") or "").strip()
    success_pattern = str(dimension_payload.get("success_pattern") or "").strip()
    failure_pattern = str(dimension_payload.get("failure_pattern") or "").strip()

    synthesis_rules = state.get("synthesis_rules", {})
    synthesis_text = "\n".join(f"- {key}: {value}" for key, value in synthesis_rules.items())

    return (
        f"Judicial Logic: {judicial_logic or 'Use synthesis_rules as binding law when judicial_logic is absent.'}\n"
        f"Success Pattern: {success_pattern or 'Not specified'}\n"
        f"Failure Pattern: {failure_pattern or 'Not specified'}\n"
        f"Synthesis Rules (Binding Law):\n{synthesis_text or '- No synthesis rules provided.'}"
    )


def _extract_opinion_text(opinion: JudicialOpinion) -> str:
    cited = "; ".join(opinion.cited_evidence) if opinion.cited_evidence else "None"
    return f"{opinion.judge} (score={opinion.score}): {opinion.argument} | cited={cited}"


def _format_prior_opinions(state: AgentState) -> str:
    opinions = state.get("opinions", [])
    if not opinions:
        return "No prior prosecutor/defense opinions were provided."

    lines = [_extract_opinion_text(opinion) for opinion in opinions if opinion.judge in {"Prosecutor", "Defense"}]
    if not lines:
        return "No prior prosecutor/defense opinions were provided."
    return "\n".join(lines)


def _invoke_structured_opinion(system_prompt: str, user_prompt: str, criterion_id: str, temperature: float, max_retries: int = 3) -> JudicialOpinion | None:
    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    ).with_structured_output(JudicialOpinion)

    for _ in range(max_retries):
        try:
            time.sleep(2)
            result = model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            if isinstance(result, JudicialOpinion) and result.argument.strip() and result.cited_evidence:
                return result.model_copy(update={"judge": "TechLead", "criterion_id": criterion_id})
        except Exception:
            continue

    return None


def tech_lead_node(state: AgentState):
    """Generate tech-lead structured opinions for every rubric criterion."""
    criterion_ids = _resolve_criterion_ids(state)
    evidence_block = _format_evidence_block(state)
    prior_opinions = _format_prior_opinions(state)

    opinions: list[JudicialOpinion] = []
    for criterion_id in criterion_ids:
        binding_law = _build_binding_law(state, criterion_id)

        system_prompt = (
            "Persona: Pragmatic Tech Lead. Focus on architectural soundness, code cleanliness, and practical viability. "
            "Return ONLY a structured JudicialOpinion object with fields: "
            "judge, criterion_id, score (1-5), argument (string), and cited_evidence (list of strings). "
            "Set judge exactly to 'TechLead'.\n\n"
            f"BINDING LAW:\n{binding_law}"
        )

        user_prompt = (
            f"Criterion ID: {criterion_id}\n\n"
            "Review the forensic evidence and both sides' arguments. "
            "Produce a tie-breaker judgment based on architecture, code quality, and delivery viability.\n\n"
            f"Evidence:\n{evidence_block}\n\n"
            f"Prior Opinions:\n{prior_opinions}"
        )

        opinion = _invoke_structured_opinion(system_prompt, user_prompt, criterion_id=criterion_id, temperature=0.2)
        if opinion is None:
            opinion = JudicialOpinion(
                judge="TechLead",
                criterion_id=criterion_id,
                score=3,
                argument="Structured tech-lead output unavailable after retries; tie-breaker confidence is limited.",
                cited_evidence=["LLM failed to return valid structured output after retries."],
            )
        opinions.append(opinion)

    return {"opinions": opinions}
