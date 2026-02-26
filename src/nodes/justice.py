from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.state import AgentState, JudicialOpinion


def _coerce_score(value: Any, default: int = 3) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(1, min(5, parsed))


def _coerce_cited_evidence(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _extract_structured(metadata: dict[str, Any], key: str) -> dict[str, Any]:
    payload = metadata.get(key, {})
    if not isinstance(payload, dict):
        payload = {}
    return {
        "score": _coerce_score(payload.get("score"), 3),
        "argument": str(payload.get("argument") or "No argument provided."),
        "cited_evidence": _coerce_cited_evidence(payload.get("cited_evidence")),
    }


def _prosecutor_flags_security(prosecutor: dict[str, Any], state: AgentState) -> bool:
    keywords = [
        "security",
        "secret",
        "credential",
        "vulnerab",
        "auth",
        "token",
        ".env",
        "id_rsa",
    ]

    prosecutor_text = (
        prosecutor.get("argument", "") + " " + " ".join(prosecutor.get("cited_evidence", []))
    ).lower()
    if any(keyword in prosecutor_text for keyword in keywords):
        return True

    evidences = state.get("evidences", [])
    for evidence in evidences:
        title = str(getattr(evidence, "title", "")).lower()
        summary = str(getattr(evidence, "summary", "")).lower()
        if "secret exposure" in title or any(keyword in summary for keyword in keywords):
            return True
    return False


def _build_dissent_summary(
    prosecutor: dict[str, Any], defense: dict[str, Any], tech_lead: dict[str, Any]
) -> str:
    return (
        "High disagreement detected between judges (score variance > 2). "
        f"Prosecutor({prosecutor['score']}): {prosecutor['argument']} | "
        f"Defense({defense['score']}): {defense['argument']} | "
        f"Tech Lead({tech_lead['score']}): {tech_lead['argument']}"
    )


def _write_markdown_report(
    state: AgentState,
    prosecutor: dict[str, Any],
    defense: dict[str, Any],
    tech_lead: dict[str, Any],
    final_score_5: float,
    final_score_100: int,
    verdict: str,
    dissent_summary: str,
    security_capped: bool,
) -> str:
    report_path = Path("reports") / "audit_results.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _list_items(items: list[str]) -> str:
        if not items:
            return "- None provided"
        return "\n".join(f"- {item}" for item in items)

    content = (
        "# Audit Results\n\n"
        f"- **Generated (UTC):** {datetime.now(timezone.utc).isoformat()}\n"
        f"- **Repository:** {state.get('repo_url', 'Unknown')}\n"
        "\n## Synthesis Rules Applied\n"
        "- **Rule of Functionality:** Tech Lead score weighted most heavily.\n"
        "- **Rule of Security:** Final score capped at 3/5 when Prosecutor flags security risk.\n"
        "- **Dissent Rule:** If variance between judges is > 2, dissent summary is generated.\n"
        f"- **Security Cap Triggered:** {'Yes' if security_capped else 'No'}\n"
        "\n## Structured Judges\n"
        f"### Prosecutor (Score: {prosecutor['score']}/5)\n"
        f"{prosecutor['argument']}\n\n"
        "**Cited Evidence**\n"
        f"{_list_items(prosecutor['cited_evidence'])}\n\n"
        f"### Defense (Score: {defense['score']}/5)\n"
        f"{defense['argument']}\n\n"
        "**Cited Evidence**\n"
        f"{_list_items(defense['cited_evidence'])}\n\n"
        f"### Tech Lead (Score: {tech_lead['score']}/5)\n"
        f"{tech_lead['argument']}\n\n"
        "**Cited Evidence**\n"
        f"{_list_items(tech_lead['cited_evidence'])}\n\n"
        "## Chief Justice Final Decision\n"
        f"- **Final Score:** {final_score_5:.2f}/5 ({final_score_100}/100)\n"
        f"- **Verdict:** {verdict}\n"
        f"- **Dissent Summary:** {dissent_summary or 'No significant dissent detected.'}\n"
    )

    report_path.write_text(content, encoding="utf-8")
    return str(report_path)


def justice_node(state: AgentState):
    metadata = state.get("metadata", {})

    prosecutor = _extract_structured(metadata, "prosecutor_structured")
    defense = _extract_structured(metadata, "defense_structured")
    tech_lead = _extract_structured(metadata, "tech_lead_structured")

    prosecutor_inverse = 6 - prosecutor["score"]

    # Rule of Functionality: tech lead weighted most heavily.
    weighted_score = (
        0.60 * tech_lead["score"]
        + 0.25 * defense["score"]
        + 0.15 * prosecutor_inverse
    )

    security_capped = _prosecutor_flags_security(prosecutor, state)
    if security_capped:
        weighted_score = min(weighted_score, 3.0)

    score_variance = max(prosecutor["score"], defense["score"], tech_lead["score"]) - min(
        prosecutor["score"], defense["score"], tech_lead["score"]
    )
    dissent_summary = ""
    if score_variance > 2:
        dissent_summary = _build_dissent_summary(prosecutor, defense, tech_lead)

    final_score_5 = round(weighted_score, 2)
    final_score_100 = int(round(final_score_5 * 20))
    verdict = "PASS" if final_score_5 >= 3.5 else "FAIL"

    reasoning = (
        f"Chief Justice synthesis: tech-lead-weighted score {final_score_5}/5. "
        f"Security cap applied: {'yes' if security_capped else 'no'}. "
        f"Judge score variance: {score_variance}."
    )
    if dissent_summary:
        reasoning += f" Dissent recorded: {dissent_summary}"

    report_path = _write_markdown_report(
        state=state,
        prosecutor=prosecutor,
        defense=defense,
        tech_lead=tech_lead,
        final_score_5=final_score_5,
        final_score_100=final_score_100,
        verdict=verdict,
        dissent_summary=dissent_summary,
        security_capped=security_capped,
    )

    return {
        "opinion": JudicialOpinion(
            score=final_score_100,
            verdict=verdict,
            recommendation="Proceed with monitored rollout." if verdict == "PASS" else "Address critical findings before release.",
            reasoning=reasoning,
        ),
        "metadata": {
            "chief_justice_score_5": final_score_5,
            "chief_justice_score_100": final_score_100,
            "chief_justice_verdict": verdict,
            "security_cap_triggered": security_capped,
            "score_variance": score_variance,
            "dissent_summary": dissent_summary,
            "audit_report_path": report_path,
        },
        "audit_completed": True,
    }
