from __future__ import annotations

import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from src.state import AgentState, AuditReport, CriterionResult, JudicialOpinion


def _resolve_criterion_ids(state: AgentState) -> list[str]:
    ids = [
        str(dimension.get("id") or "")
        for dimension in state.get("rubric_dimensions", [])
        if isinstance(dimension, dict)
    ]
    return ids if ids else ["documentation_coverage", "langgraph_usage", "security_hardening"]


def _invoke_structured_opinion(
    system_prompt: str,
    user_prompt: str,
    criterion_id: str,
    judge_name: str,
    model_name: str,
    temperature: float,
) -> JudicialOpinion | None:
    try:
        llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            groq_api_key=os.getenv("GROQ_API_KEY"),
        ).with_structured_output(JudicialOpinion)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        if response:
            return response.model_copy(update={"judge": judge_name, "criterion_id": criterion_id})
    except Exception:
        return None
    return None


def prosecutor_node(state: AgentState):
    opinions: list[JudicialOpinion] = []
    for criterion_id in _resolve_criterion_ids(state):
        opinion = _invoke_structured_opinion(
            "Strict Prosecutor. Find flaws.",
            f"Audit {criterion_id}",
            criterion_id,
            "Prosecutor",
            "llama-3.1-8b-instant",
            0.1,
        )
        if opinion:
            opinions.append(opinion)
    return {"opinions": opinions}


def defense_node(state: AgentState):
    opinions: list[JudicialOpinion] = []
    for criterion_id in _resolve_criterion_ids(state):
        opinion = _invoke_structured_opinion(
            "Defense Counsel. Highlight strengths.",
            f"Audit {criterion_id}",
            criterion_id,
            "Defense",
            "llama-3.1-8b-instant",
            0.1,
        )
        if opinion:
            opinions.append(opinion)
    return {"opinions": opinions}


def tech_lead_node(state: AgentState):
    opinions: list[JudicialOpinion] = []
    for criterion_id in _resolve_criterion_ids(state):
        opinion = _invoke_structured_opinion(
            "Tech Lead. Neutral arbitrator.",
            f"Audit {criterion_id}",
            criterion_id,
            "TechLead",
            "llama-3.1-8b-instant",
            0.1,
        )
        if opinion:
            opinions.append(opinion)
    return {"opinions": opinions}


def _get_dimension_id(raw_dimension: dict) -> str:
    return str(
        raw_dimension.get("id")
        or raw_dimension.get("dimension_id")
        or raw_dimension.get("criterion_id")
        or "general"
    )


def _get_dimension_name(raw_dimension: dict, fallback_id: str) -> str:
    return str(
        raw_dimension.get("name")
        or raw_dimension.get("dimension_name")
        or raw_dimension.get("title")
        or fallback_id
    )


def _group_opinions_by_dimension(opinions: list[JudicialOpinion]) -> dict[str, list[JudicialOpinion]]:
    grouped: dict[str, list[JudicialOpinion]] = {}
    for opinion in opinions:
        grouped.setdefault(opinion.criterion_id, []).append(opinion)
    return grouped


def _find_judge_opinion(opinions: list[JudicialOpinion], judge: str) -> JudicialOpinion | None:
    for opinion in opinions:
        if opinion.judge == judge:
            return opinion
    return None


def _contains_security_signal(text: str) -> bool:
    keywords = (
        "security",
        "vulnerab",
        "credential",
        "token",
        "secret",
        "auth",
        "exposed",
        "leak",
        "injection",
        "xss",
        "sql",
        "rce",
        "cve",
    )
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _security_cap_triggered(state: AgentState, dimension_id: str, prosecutor: JudicialOpinion) -> bool:
    prosecutor_text = (prosecutor.argument + " " + " ".join(prosecutor.cited_evidence)).strip()
    has_security_context = _contains_security_signal(prosecutor_text)
    has_confirmation = any(word in prosecutor_text.lower() for word in ("confirm", "confirmed", "found", "verified", "present"))

    if has_security_context and (has_confirmation or prosecutor.score <= 2):
        return True

    evidence_map = state.get("evidences", {})
    for evidence in evidence_map.get(dimension_id, []):
        goal = str(getattr(evidence, "goal", ""))
        content = str(getattr(evidence, "content", "") or "")
        rationale = str(getattr(evidence, "rationale", ""))
        found = bool(getattr(evidence, "found", False))
        if found and _contains_security_signal(f"{goal} {content} {rationale}") and has_security_context:
            return True

    return False


def _fact_supremacy_triggered(state: AgentState, dimension_id: str, prosecutor: JudicialOpinion) -> bool:
    prosecutor_text = (prosecutor.argument + " " + " ".join(prosecutor.cited_evidence)).strip().lower()
    prosecutor_asserts_finding = any(word in prosecutor_text for word in ("confirm", "confirmed", "found", "verified", "present"))

    evidence_map = state.get("evidences", {})
    has_confirmed_security_evidence = False
    for evidence in evidence_map.get(dimension_id, []):
        goal = str(getattr(evidence, "goal", ""))
        content = str(getattr(evidence, "content", "") or "")
        rationale = str(getattr(evidence, "rationale", ""))
        found = bool(getattr(evidence, "found", False))
        if found and _contains_security_signal(f"{goal} {content} {rationale}"):
            has_confirmed_security_evidence = True
            break

    return prosecutor_asserts_finding and has_confirmed_security_evidence


def _apply_security_override(weighted_score: float, dimension_id: str, prosecutor: JudicialOpinion, fact_supremacy: bool) -> tuple[float, bool]:
    if not fact_supremacy:
        return weighted_score, False

    if dimension_id == "safe_tool_engineering" and prosecutor.score <= 2:
        return min(weighted_score, 2.0), True

    if _contains_security_signal(prosecutor.argument) and prosecutor.score <= 2:
        return min(weighted_score, 3.0), True

    return weighted_score, False


def _compute_weighted_score(prosecutor: JudicialOpinion, defense: JudicialOpinion, tech_lead: JudicialOpinion) -> float:
    return (
        0.20 * prosecutor.score
        + 0.25 * defense.score
        + 0.55 * tech_lead.score
    )


def _build_dissent_summary(prosecutor: JudicialOpinion, defense: JudicialOpinion, tech_lead: JudicialOpinion) -> str:
    return (
        "High disagreement detected (score variance > 2). "
        f"Prosecutor={prosecutor.score}: {prosecutor.argument} | "
        f"Defense={defense.score}: {defense.argument} | "
        f"TechLead={tech_lead.score}: {tech_lead.argument}"
    )


def _build_remediation(final_score: int, security_capped: bool, dissent_summary: str) -> str:
    if security_capped:
        return "Address confirmed security vulnerability immediately and rerun full audit before release."
    if dissent_summary:
        return "Run adjudication review to reconcile conflicting judge assessments and gather missing evidence."
    if final_score <= 2:
        return "Prioritize architectural refactoring and reliability fixes before deployment."
    if final_score == 3:
        return "Implement targeted fixes and verify quality gates with a follow-up audit."
    return "Maintain current implementation quality and continue monitoring with routine audits."


def _build_executive_summary(criteria: list[CriterionResult], overall_score: float) -> str:
    failed = [item for item in criteria if item.final_score < 3.5]
    if not criteria:
        return "Audit completed with no scored dimensions. Insufficient evidence and opinions were provided."
    if failed:
        return (
            f"Audit completed with overall score {overall_score:.2f}/5. "
            f"{len(failed)} dimension(s) require immediate remediation before release."
        )
    return f"Audit completed successfully with overall score {overall_score:.2f}/5 and no failing dimensions."


def _build_remediation_plan(criteria: list[CriterionResult]) -> str:
    if not criteria:
        return "Collect rubric-aligned evidence and run all judge nodes before generating a final decision."

    lines = [
        f"- {criterion.dimension_name} ({criterion.dimension_id}): {criterion.remediation}"
        for criterion in criteria
    ]
    return "\n".join(lines)


def _render_report_markdown(report: AuditReport) -> str:
    lines = [
        "# Audit Results",
        "",
        f"- **Repository:** {report.repo_url}",
        f"- **Overall Score:** {report.overall_score}/5",
        f"- **Final Verdict:** {report.audit_verdict}",
        "",
        "## Executive Summary",
        report.executive_summary,
        "",
        "## Criterion Breakdown",
    ]

    for criterion in report.criteria:
        lines.extend(
            [
                "",
                f"### {criterion.dimension_name} ({criterion.dimension_id})",
                "#### Final Score",
                f"{criterion.final_score}/5",
                "#### Cited Line Numbers",
                (
                    ", ".join(str(line) for line in criterion.cited_line_numbers)
                    if criterion.cited_line_numbers
                    else "No line-level citations available."
                ),
                "#### Dissent Summary",
                criterion.dissent_summary or "No significant dissent detected.",
                "#### Remediation",
                criterion.remediation,
                "#### Judge Opinions",
            ]
        )
        for opinion in criterion.judge_opinions:
            lines.append(
                f"  - {opinion.judge}: score={opinion.score}, argument={opinion.argument}"
            )

    lines.extend(["", "## Remediation Plan", report.remediation_plan])
    for criterion in report.criteria:
        lines.extend(
            [
                "",
                f"### {criterion.dimension_name} ({criterion.dimension_id})",
            ]
        )
        if criterion.file_fix_instructions:
            lines.extend([f"- {fix_step}" for fix_step in criterion.file_fix_instructions])
        else:
            lines.append("- No file-level fix instructions required.")

    lines.append("")
    return "\n".join(lines)


def _write_final_markdown(report: AuditReport) -> str:
    file_path = os.path.join("audit", "report_onself_generated", "audit_report.md")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as report_file:
        report_file.write(_render_report_markdown(report))
    return file_path


def _compute_evidence_found_score(state: AgentState) -> tuple[float, int, int]:
    evidence_map = state.get("evidences", {}) or {}
    evidence_items: list = []

    if isinstance(evidence_map, dict):
        for value in evidence_map.values():
            if isinstance(value, list):
                evidence_items.extend(value)
            elif value is not None:
                evidence_items.append(value)
    elif isinstance(evidence_map, list):
        evidence_items.extend(evidence_map)

    total_count = 0
    found_count = 0

    for evidence in evidence_items:
        total_count += 1
        if isinstance(evidence, dict):
            raw_found_value = evidence.get("found", False)
        else:
            raw_found_value = getattr(evidence, "found", False)

        if isinstance(raw_found_value, str):
            found_value = raw_found_value.strip().lower() in {"true", "1", "yes", "y", "found", "✅ found"}
        else:
            found_value = bool(raw_found_value)

        if found_value:
            found_count += 1

    if total_count == 0:
        return 0.0, 0, 0

    score_float = round((found_count / total_count) * 5, 2)
    return score_float, found_count, total_count


def justice_node(state: AgentState):
    opinions = state.get("opinions", [])
    rubric_dimensions = state.get("rubric_dimensions", [])

    grouped_opinions = _group_opinions_by_dimension(opinions)

    dimension_specs: list[tuple[str, str]] = []
    for raw_dimension in rubric_dimensions:
        if isinstance(raw_dimension, dict):
            dimension_id = _get_dimension_id(raw_dimension)
            dimension_name = _get_dimension_name(raw_dimension, dimension_id)
            dimension_specs.append((dimension_id, dimension_name))

    if not dimension_specs:
        known_dimension_ids = list(grouped_opinions.keys()) or list(state.get("evidences", {}).keys())
        if not known_dimension_ids:
            known_dimension_ids = ["general"]
        dimension_specs = [(dimension_id, dimension_id) for dimension_id in known_dimension_ids]

    criteria_results: list[CriterionResult] = []
    missing_pairs: list[str] = []

    for dimension_id, dimension_name in dimension_specs:
        dimension_opinions = grouped_opinions.get(dimension_id, [])
        prosecutor = _find_judge_opinion(dimension_opinions, "Prosecutor")
        defense = _find_judge_opinion(dimension_opinions, "Defense")
        tech_lead = _find_judge_opinion(dimension_opinions, "TechLead")

        if prosecutor is None:
            missing_pairs.append(f"{dimension_id}:Prosecutor")
        if defense is None:
            missing_pairs.append(f"{dimension_id}:Defense")
        if tech_lead is None:
            missing_pairs.append(f"{dimension_id}:TechLead")
        if prosecutor is None or defense is None or tech_lead is None:
            continue

        weighted_score = _compute_weighted_score(prosecutor, defense, tech_lead)

        security_capped = _security_cap_triggered(state, dimension_id, prosecutor)
        fact_supremacy = _fact_supremacy_triggered(state, dimension_id, prosecutor)
        if security_capped:
            weighted_score = min(weighted_score, 3.0)

        weighted_score, security_override_applied = _apply_security_override(
            weighted_score,
            dimension_id,
            prosecutor,
            fact_supremacy,
        )
        security_capped = security_capped or security_override_applied

        score_variance = max(prosecutor.score, defense.score, tech_lead.score) - min(
            prosecutor.score, defense.score, tech_lead.score
        )
        dissent_summary = ""
        if score_variance > 2:
            dissent_summary = _build_dissent_summary(prosecutor, defense, tech_lead)

        final_score = int(round(weighted_score))
        final_score = max(1, min(5, final_score))

        remediation = _build_remediation(final_score, security_capped, dissent_summary)

        criteria_results.append(
            CriterionResult(
                dimension_id=dimension_id,
                dimension_name=dimension_name,
                final_score=final_score,
                judge_opinions=[prosecutor, defense, tech_lead],
                dissent_summary=dissent_summary or None,
                remediation=remediation,
            )
        )

    if missing_pairs:
        return {
            "final_report": None,
            "overall_score": None,
            "final_report_path": None,
            "audit_completed": False,
        }

    overall_score = round(
        sum(criterion.final_score for criterion in criteria_results) / max(len(criteria_results), 1),
        2,
    )

    report = AuditReport(
        repo_url=state.get("repo_url", "Unknown repository"),
        executive_summary=_build_executive_summary(criteria_results, overall_score),
        overall_score=overall_score,
        audit_verdict="PASS" if overall_score >= 3.5 else "FAIL",
        criteria=criteria_results,
        remediation_plan=_build_remediation_plan(criteria_results),
    )

    final_report_path = _write_final_markdown(report)

    return {
        "final_report": report,
        "overall_score": overall_score,
        "final_report_path": final_report_path,
        "audit_completed": True,
    }


def chief_justice_node(state: AgentState):
    opinions = state.get("opinions", [])
    grouped_opinions = _group_opinions_by_dimension(opinions)
    evidence_map = state.get("evidences", {}) or {}
    rubric_dimensions = state.get("rubric_dimensions", [])

    dimension_specs: list[tuple[str, str]] = []
    for raw_dimension in rubric_dimensions:
        if isinstance(raw_dimension, dict):
            dimension_id = _get_dimension_id(raw_dimension)
            dimension_name = _get_dimension_name(raw_dimension, dimension_id)
            dimension_specs.append((dimension_id, dimension_name))

    if not dimension_specs:
        known_dimension_ids = list(grouped_opinions.keys()) or list(evidence_map.keys())
        if not known_dimension_ids:
            known_dimension_ids = ["general"]
        dimension_specs = [(dimension_id, dimension_id) for dimension_id in known_dimension_ids]

    criteria_results: list[CriterionResult] = []
    criterion_scores: list[float] = []
    low_score_findings: list[tuple[str, float, str]] = []
    dissent_required = False
    dissent_records: list[str] = []

    def _normalized(text: str) -> str:
        return (text or "").strip().lower()

    def _criterion_is_security(criterion_id: str) -> bool:
        cid = _normalized(criterion_id)
        return "security" in cid or cid == "safe_tool_engineering"

    def _criterion_is_architecture(criterion_id: str) -> bool:
        cid = _normalized(criterion_id)
        return "architecture" in cid or "graph" in cid

    def _criterion_matches_evidence_key(criterion_id: str, evidence_key: str) -> bool:
        cid = _normalized(criterion_id)
        ek = _normalized(evidence_key)
        key_matches = bool(cid and (cid in ek or ek in cid))
        if key_matches:
            return True
        if _criterion_is_architecture(criterion_id) and ek in {"langgraph_usage", "swarm_visual"}:
            return True
        if _criterion_is_security(criterion_id) and ek in {"security_hardening", "safe_tool_engineering"}:
            return True
        return False

    def _extract_confidence(raw_evidence: object) -> float | None:
        raw_value = raw_evidence.get("confidence") if isinstance(raw_evidence, dict) else getattr(raw_evidence, "confidence", None)
        if raw_value is None:
            return None
        try:
            confidence = float(raw_value)
        except Exception:
            return None
        return max(0.0, min(1.0, confidence))

    def _repo_confidence_for_criterion(criterion_id: str) -> float | None:
        matched_confidences: list[float] = []

        for evidence_key, evidence_list in evidence_map.items():
            if not _criterion_matches_evidence_key(criterion_id, str(evidence_key)):
                continue

            for evidence in evidence_list or []:
                confidence = _extract_confidence(evidence)
                if confidence is not None:
                    matched_confidences.append(confidence)

        if not matched_confidences:
            return None
        return min(matched_confidences)

    def _criterion_lines_and_files(criterion_id: str) -> tuple[list[int], list[str]]:
        line_numbers: set[int] = set()
        file_locations: set[str] = set()

        for evidence_key, evidence_list in evidence_map.items():
            if not _criterion_matches_evidence_key(criterion_id, str(evidence_key)):
                continue

            for evidence in evidence_list or []:
                if isinstance(evidence, dict):
                    source_line = evidence.get("source_line", -1)
                    location = str(evidence.get("location", "")).strip()
                else:
                    source_line = getattr(evidence, "source_line", -1)
                    location = str(getattr(evidence, "location", "")).strip()

                try:
                    source_line_int = int(source_line)
                except Exception:
                    source_line_int = -1

                if source_line_int > 0:
                    line_numbers.add(source_line_int)
                if location:
                    file_locations.add(location.replace("\\", "/"))

        return sorted(line_numbers), sorted(file_locations)

    def _generate_dissent_summary(record_lines: list[str]) -> str:
        if not record_lines:
            return "No dissent summary required."

        prompt = "\n".join(record_lines)
        try:
            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                temperature=0.1,
                groq_api_key=os.getenv("GROQ_API_KEY"),
            )
            response = llm.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are a Chief Justice summarizer. Produce a concise dissent summary focusing on "
                            "score conflicts and evidence certainty gaps."
                        )
                    ),
                    HumanMessage(content=prompt),
                ]
            )
            content = str(getattr(response, "content", "")).strip()
            if content:
                return content
        except Exception:
            pass

        return "Dissent detected: judge score spread exceeded threshold and requires manual adjudication review."

    def _remediation_step(criterion_id: str, prosecutor_argument: str) -> str:
        criterion_key = criterion_id.lower()
        argument_key = (prosecutor_argument or "").lower()

        if "graph" in criterion_key or "langgraph" in criterion_key:
            return f"Fix LangGraph documentation and flow clarity for `{criterion_id}` in README.md and architecture notes."
        if "git" in criterion_key or "commit" in argument_key:
            return f"Increase commit frequency for `{criterion_id}` with smaller, atomic commits and clearer commit messages."
        if "state" in criterion_key:
            return f"Strengthen state update consistency for `{criterion_id}` by enforcing typed keys and deterministic merge rules."
        if "structured" in criterion_key or "output" in criterion_key:
            return f"Enforce strict structured output validation for `{criterion_id}` and add schema conformance checks."
        if "safe_tool" in criterion_key or "security" in criterion_key:
            return f"Harden `{criterion_id}` by adding explicit security checks and documenting secure tool usage constraints."
        if prosecutor_argument:
            return f"Address `{criterion_id}` gaps noted by Prosecutor: {prosecutor_argument}"
        return f"Create a targeted improvement plan for `{criterion_id}` and rerun the audit after implementing fixes."

    for criterion_id, dimension_name in dimension_specs:
        criterion_opinions = grouped_opinions.get(criterion_id, [])
        prosecutor = _find_judge_opinion(criterion_opinions, "Prosecutor")
        defense = _find_judge_opinion(criterion_opinions, "Defense")
        tech_lead = _find_judge_opinion(criterion_opinions, "TechLead")
        repo_confidence = _repo_confidence_for_criterion(criterion_id)
        cited_lines, evidence_files = _criterion_lines_and_files(criterion_id)

        weighted_scores: list[float] = []
        scored_values_for_variance: list[float] = []

        for judge_name, opinion in [("Prosecutor", prosecutor), ("Defense", defense), ("TechLead", tech_lead)]:
            if opinion is None:
                continue

            score_value = float(opinion.score)
            scored_values_for_variance.append(score_value)

            if repo_confidence is not None and repo_confidence < 0.5 and score_value >= 4.0:
                continue

            if _criterion_is_architecture(criterion_id) and judge_name == "TechLead":
                weighted_scores.append(score_value * 0.5)
            elif _criterion_is_architecture(criterion_id):
                weighted_scores.append(score_value * 0.25)
            else:
                weighted_scores.append(score_value)

        criterion_score = round(sum(weighted_scores), 2) if _criterion_is_architecture(criterion_id) else (
            round(sum(weighted_scores) / len(weighted_scores), 2) if weighted_scores else 0.0
        )

        if weighted_scores:
            criterion_scores.append(criterion_score)

        if len(scored_values_for_variance) >= 2:
            score_variance = max(scored_values_for_variance) - min(scored_values_for_variance)
            if score_variance > 2.5:
                dissent_required = True
                dissent_records.append(
                    " | ".join(
                        [
                            f"criterion={criterion_id}",
                            f"variance={score_variance:.2f}",
                            f"prosecutor={prosecutor.score if prosecutor else 'NA'}",
                            f"defense={defense.score if defense else 'NA'}",
                            f"tech_lead={tech_lead.score if tech_lead else 'NA'}",
                            f"repo_confidence={repo_confidence if repo_confidence is not None else 'NA'}",
                        ]
                    )
                )

        if criterion_score < 4.0:
            low_score_findings.append(
                (
                    criterion_id,
                    criterion_score,
                    prosecutor.argument if prosecutor else "",
                )
            )

        file_fix_instructions: list[str] = []
        if criterion_score < 4.0:
            if evidence_files:
                for file_location in evidence_files[:3]:
                    file_fix_instructions.append(f"Fix {criterion_id} issues in {file_location}")
            else:
                file_fix_instructions.append(f"Fix {criterion_id} issues in relevant source files and supporting docs")
            file_fix_instructions.append(_remediation_step(criterion_id, prosecutor.argument if prosecutor else ""))

        criteria_results.append(
            CriterionResult(
                dimension_id=criterion_id,
                dimension_name=dimension_name,
                final_score=max(1, min(5, int(round(criterion_score if criterion_score > 0 else 1.0)))),
                judge_opinions=[op for op in [prosecutor, defense, tech_lead] if op is not None],
                dissent_summary=(
                    _build_dissent_summary(prosecutor, defense, tech_lead)
                    if prosecutor and defense and tech_lead and (max(prosecutor.score, defense.score, tech_lead.score) - min(prosecutor.score, defense.score, tech_lead.score) > 2.5)
                    else None
                ),
                remediation=_remediation_step(criterion_id, prosecutor.argument if prosecutor else ""),
                cited_line_numbers=cited_lines,
                file_fix_instructions=file_fix_instructions,
            )
        )

    if criterion_scores:
        score_float = round(sum(criterion_scores) / len(criterion_scores), 2)
        executive_summary = (
            f"Audit completed across {len(criterion_scores)} criterion areas with an overall score of "
            f"{score_float:.1f}/5."
        )
    else:
        score_float, found_count, total_count = _compute_evidence_found_score(state)
        executive_summary = (
            "No judicial opinions were available, so the overall score was derived from collected evidence "
            f"({found_count}/{total_count} findings marked as found)."
        )

    security_triggered = False
    for criterion_id, criterion_opinions in grouped_opinions.items():
        if not _criterion_is_security(criterion_id):
            continue
        prosecutor = _find_judge_opinion(criterion_opinions, "Prosecutor")
        if prosecutor and float(prosecutor.score) < 2.0:
            security_triggered = True
            break

    if security_triggered:
        score_float = min(score_float, 3.0)

    overall_score = f"{score_float:.1f}"
    verdict_string = "DISSENT_DETECTED" if dissent_required else ("PASS" if score_float >= 3.5 else "FAIL")

    remediation_lines = []
    if low_score_findings:
        for criterion_id, criterion_score, prosecutor_argument in low_score_findings:
            remediation_lines.append(
                f"- {criterion_id} ({criterion_score:.2f}/5): {_remediation_step(criterion_id, prosecutor_argument)}"
            )
    else:
        remediation_lines.append("- No critical remediation needed. Maintain current quality and continue monitoring.")

    dissent_summary_text = _generate_dissent_summary(dissent_records) if dissent_required else "No dissent detected."

    executive_summary = (
        f"Verdict: {verdict_string}. Overall Score: {overall_score}/5. "
        f"{executive_summary}"
    )

    report = AuditReport(
        repo_url=state.get("repo_url", "Unknown repository"),
        executive_summary=executive_summary,
        overall_score=float(overall_score),
        audit_verdict=verdict_string,
        criteria=criteria_results,
        remediation_plan="\n".join(remediation_lines) + f"\n\nDissent Summary: {dissent_summary_text}",
    )

    full_report_content = _render_report_markdown(report)

    out_path = Path("audit") / "report_onself_generated" / "audit_report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_report_content, encoding="utf-8")

    print(f"Final Score Calculated: {overall_score}")
    return {
        "final_report": full_report_content,
        "overall_score": overall_score,
        "audit_verdict": verdict_string,
        "final_report_path": out_path.as_posix(),
        "audit_completed": True,
    }
