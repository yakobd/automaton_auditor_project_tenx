import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.state import AgentState, JudicialOpinion


def _format_evidence_block(state: AgentState) -> str:
    evidence_map = state.get("evidences", {})
    if not evidence_map:
        return "No evidences were collected."

    lines: list[str] = []
    item_index = 1
    for dimension, evidences in evidence_map.items():
        for evidence in evidences:
            goal = getattr(evidence, "goal", "Unknown goal")
            found = getattr(evidence, "found", False)
            content = getattr(evidence, "content", "")
            location = getattr(evidence, "location", "Unknown")
            rationale = getattr(evidence, "rationale", "")
            confidence = getattr(evidence, "confidence", "N/A")
            lines.append(
                f"{item_index}. Dimension: {dimension}\n"
                f"   Goal: {goal}\n"
                f"   Found: {found}\n"
                f"   Location: {location}\n"
                f"   Content: {content or 'N/A'}\n"
                f"   Rationale: {rationale}\n"
                f"   Confidence: {confidence}"
            )
            item_index += 1

    if not lines:
        return "No evidences were collected."

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


def _invoke_structured_opinion(
    system_prompt: str,
    user_prompt: str,
    criterion_id: str,
    judge_name: str,
    model_name: str,
    temperature: float,
) -> JudicialOpinion | None:
    model = ChatGroq(
        model=model_name,
        temperature=temperature,
        groq_api_key=os.getenv("GROQ_API_KEY"),
    ).with_structured_output(JudicialOpinion)

    def _is_valid(result: JudicialOpinion | None) -> bool:
        return bool(
            isinstance(result, JudicialOpinion)
            and result.argument.strip()
            and result.cited_evidence
        )

    try:
        result = model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        if _is_valid(result):
            return result.model_copy(update={"judge": judge_name, "criterion_id": criterion_id})
    except Exception:
        pass

    fallback_system_prompt = (
        "Return ONLY a structured JudicialOpinion. "
        f"Set judge='{judge_name}' and criterion_id='{criterion_id}'. "
        "Use score 1-5, a short concrete argument, and at least one cited_evidence item."
    )
    fallback_user_prompt = (
        f"Criterion: {criterion_id}\n"
        "Create a concise, evidence-grounded judgment from the available material."
    )

    try:
        fallback_result = model.invoke(
            [
                SystemMessage(content=fallback_system_prompt),
                HumanMessage(content=fallback_user_prompt),
            ]
        )
        if _is_valid(fallback_result):
            return fallback_result.model_copy(update={"judge": judge_name, "criterion_id": criterion_id})
    except Exception:
        pass

    return None


def prosecutor_node(state: AgentState):
    evidence_block = _format_evidence_block(state)
    repo_url = state.get("repo_url", "Unknown repository")
    criterion_ids = _resolve_criterion_ids(state)

    opinions: list[JudicialOpinion] = []
    for criterion_id in criterion_ids:
        binding_law = _build_binding_law(state, criterion_id)

        system_prompt = (
            "You are a skeptical senior software auditor acting as a prosecutor. "
            "Return ONLY a structured JudicialOpinion object with fields: "
            "judge, criterion_id, score (1-5), argument (string), and cited_evidence (list of strings). "
            "Set judge exactly to 'Prosecutor'. Do not invent facts; cite only provided evidence.\n\n"
            f"BINDING LAW:\n{binding_law}"
        )

        user_prompt = (
            f"Repository under audit: {repo_url}\n"
            f"Criterion ID: {criterion_id}\n\n"
            "Collected evidence:\n"
            f"{evidence_block}\n\n"
            "Produce a harsh prosecution argument focused on reliability, security, and process risk."
        )

        opinion = _invoke_structured_opinion(
            system_prompt,
            user_prompt,
            criterion_id=criterion_id,
            judge_name="Prosecutor",
            model_name="llama-3.1-8b-instant",
            temperature=0.2,
        )
        if opinion is None:
            opinion = JudicialOpinion(
                judge="Prosecutor",
                criterion_id=criterion_id,
                score=3,
                argument="Prosecutor fallback opinion applied; risk remains and requires verification.",
                cited_evidence=["Fallback judgment generated after model output validation failed twice."],
            )
        opinions.append(opinion)

    return {"opinions": opinions}


def defense_node(state: AgentState):
    evidence_block = _format_evidence_block(state)
    repo_url = state.get("repo_url", "Unknown repository")
    criterion_ids = _resolve_criterion_ids(state)

    opinions: list[JudicialOpinion] = []
    for criterion_id in criterion_ids:
        binding_law = _build_binding_law(state, criterion_id)

        system_prompt = (
            "You are a supportive senior architect acting as defense counsel. "
            "Return ONLY a structured JudicialOpinion object with fields: "
            "judge, criterion_id, score (1-5), argument (string), and cited_evidence (list of strings). "
            "Set judge exactly to 'Defense'. Highlight strengths and practical viability, but stay grounded in evidence.\n\n"
            f"BINDING LAW:\n{binding_law}"
        )

        user_prompt = (
            f"Repository under audit: {repo_url}\n"
            f"Criterion ID: {criterion_id}\n\n"
            "Collected evidence:\n"
            f"{evidence_block}\n\n"
            "Produce a defense argument that emphasizes pragmatic strengths and realistic mitigation paths."
        )

        time.sleep(2)
        opinion = _invoke_structured_opinion(
            system_prompt,
            user_prompt,
            criterion_id=criterion_id,
            judge_name="Defense",
            model_name="llama-3.1-8b-instant",
            temperature=0.4,
        )
        if opinion is None:
            opinion = JudicialOpinion(
                judge="Defense",
                criterion_id=criterion_id,
                score=3,
                argument="Defense fallback opinion applied; strengths exist but need additional corroboration.",
                cited_evidence=["Fallback judgment generated after model output validation failed twice."],
            )
        opinions.append(opinion)

    return {"opinions": opinions}


def tech_lead_node(state: AgentState):
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

        time.sleep(6)
        opinion = _invoke_structured_opinion(
            system_prompt,
            user_prompt,
            criterion_id=criterion_id,
            judge_name="TechLead",
            model_name="llama-3.3-70b-versatile",
            temperature=0.2,
        )
        if opinion is None:
            opinion = JudicialOpinion(
                judge="TechLead",
                criterion_id=criterion_id,
                score=3,
                argument="TechLead fallback opinion applied; tie-breaker confidence is moderate pending deeper review.",
                cited_evidence=["Fallback judgment generated after model output validation failed twice."],
            )
        opinions.append(opinion)

    return {"opinions": opinions}


def _group_by_criterion(opinions: list[JudicialOpinion]) -> dict[str, list[JudicialOpinion]]:
    grouped: dict[str, list[JudicialOpinion]] = {}
    for opinion in opinions:
        grouped.setdefault(opinion.criterion_id, []).append(opinion)
    return grouped


def _collect_dimension_ids(state: AgentState, grouped: dict[str, list[JudicialOpinion]]) -> list[str]:
    dimension_ids: list[str] = []

    for raw_dimension in state.get("rubric_dimensions", []):
        if isinstance(raw_dimension, dict):
            dimension_id = str(
                raw_dimension.get("id")
                or raw_dimension.get("dimension_id")
                or raw_dimension.get("criterion_id")
                or ""
            ).strip()
            if dimension_id and dimension_id not in dimension_ids:
                dimension_ids.append(dimension_id)

    for dimension_id in state.get("evidences", {}).keys():
        if dimension_id not in dimension_ids:
            dimension_ids.append(dimension_id)

    for dimension_id in grouped.keys():
        if dimension_id not in dimension_ids:
            dimension_ids.append(dimension_id)

    if not dimension_ids:
        dimension_ids.append("general")

    return dimension_ids


def _dedupe_opinions(opinions: list[JudicialOpinion]) -> list[JudicialOpinion]:
    deduped: list[JudicialOpinion] = []
    seen_pairs: set[tuple[str, str]] = set()
    for opinion in opinions:
        key = (opinion.criterion_id, opinion.judge)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped.append(opinion)
    return deduped


def judge_node(state: AgentState):
    """Validate complete per-criterion coverage from all three judges without neutral fallback."""
    opinions = state.get("opinions", [])
    opinions = _dedupe_opinions(opinions)
    grouped = _group_by_criterion(opinions)
    dimension_ids = _collect_dimension_ids(state, grouped)

    required_judges = ("Prosecutor", "Defense", "TechLead")
    missing_pairs: list[str] = []

    for dimension_id in dimension_ids:
        criterion_opinions = grouped.get(dimension_id, [])
        for judge in required_judges:
            if not any(opinion.judge == judge for opinion in criterion_opinions):
                missing_pairs.append(f"{dimension_id}:{judge}")

    if missing_pairs:
        return {"audit_completed": False}

    return {"opinions": opinions}
