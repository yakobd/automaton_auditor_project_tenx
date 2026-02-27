from src.state import AgentState, JudicialOpinion


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
