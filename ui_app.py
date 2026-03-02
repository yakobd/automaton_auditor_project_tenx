import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.graph import graph
from src.state import AuditReport


st.set_page_config(page_title="LangGraph Auditor", layout="wide")

REPORTS_DIR = Path("audit") / "report_onself_generated"


def _load_rubric() -> tuple[list[dict], dict]:
    rubric_path = Path("rubric") / "rubric.json"
    try:
        with rubric_path.open("r", encoding="utf-8") as rubric_file:
            payload = json.load(rubric_file)
        dimensions = payload.get("dimensions", [])
        synthesis_rules = payload.get("synthesis_rules", {})
        if not isinstance(dimensions, list):
            dimensions = []
        if not isinstance(synthesis_rules, dict):
            synthesis_rules = {}
        return dimensions, synthesis_rules
    except Exception:
        return [], {}


def _extract_repo_owner(repo_url: str) -> str:
    cleaned = (repo_url or "").strip().rstrip("/")
    marker = "github.com/"
    if marker not in cleaned:
        return "unknown_user"

    tail = cleaned.split(marker, 1)[1]
    owner = tail.split("/", 1)[0].strip()
    safe_owner = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in owner)
    return safe_owner or "unknown_user"


def _get_judge_scores(final_state: dict) -> dict[str, float]:
    opinions = final_state.get("opinions", []) or []
    score_buckets: dict[str, list[float]] = {"Prosecutor": [], "Defense": [], "TechLead": []}

    for opinion in opinions:
        if isinstance(opinion, dict):
            judge = str(opinion.get("judge", "")).strip()
            score = opinion.get("score")
        else:
            judge = str(getattr(opinion, "judge", "")).strip()
            score = getattr(opinion, "score", None)

        if judge not in score_buckets:
            continue
        try:
            score_buckets[judge].append(float(score))
        except Exception:
            continue

    return {
        "Prosecutor": round(sum(score_buckets["Prosecutor"]) / len(score_buckets["Prosecutor"]), 2)
        if score_buckets["Prosecutor"]
        else 0.0,
        "Defense": round(sum(score_buckets["Defense"]) / len(score_buckets["Defense"]), 2)
        if score_buckets["Defense"]
        else 0.0,
        "Tech Lead": round(sum(score_buckets["TechLead"]) / len(score_buckets["TechLead"]), 2)
        if score_buckets["TechLead"]
        else 0.0,
    }


def _render_markdown_report(final_state: dict) -> str:
    final_report = final_state.get("final_report")

    if isinstance(final_report, str):
        return final_report

    if isinstance(final_report, dict):
        try:
            report_obj = AuditReport.model_validate(final_report)
            return _report_to_markdown(report_obj)
        except Exception:
            return "## Audit Report\n\nFinal report exists but could not be parsed into markdown."

    if final_report is not None and hasattr(final_report, "model_dump"):
        try:
            report_obj = AuditReport.model_validate(final_report.model_dump())
            return _report_to_markdown(report_obj)
        except Exception:
            return "## Audit Report\n\nFinal report exists but could not be parsed into markdown."

    return "## Audit Report\n\nNo final report generated."


def _report_to_markdown(report: AuditReport) -> str:
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
                "#### Dissent Summary",
                criterion.dissent_summary or "No significant dissent detected.",
                "#### Remediation",
                criterion.remediation,
            ]
        )

    lines.extend(["", "## Remediation Plan", report.remediation_plan, ""])
    return "\n".join(lines)


def _build_initial_state(repo_url: str) -> dict:
    rubric_dimensions, synthesis_rules = _load_rubric()
    return {
        "repo_url": repo_url,
        "repo_owner": _extract_repo_owner(repo_url),
        "repo_path": None,
        "rubric_dimensions": rubric_dimensions,
        "synthesis_rules": synthesis_rules,
        "evidences": {},
        "opinions": [],
        "final_report": None,
        "overall_score": None,
        "audit_verdict": None,
        "final_report_path": None,
        "audit_completed": False,
    }


def _run_audit_with_live_updates(initial_state: dict, status_col, logs_col) -> dict:
    latest_state = dict(initial_state)

    with status_col:
        with st.status("Running LangGraph audit...", expanded=True) as run_status:
            for output in graph.stream(initial_state, stream_mode="updates"):
                for node_name, state_update in output.items():
                    latest_state.update(state_update)
                    st.write(f"✅ {node_name} completed")
            run_status.update(label="Audit complete", state="complete")

    with logs_col:
        st.subheader("Execution Notes")
        st.write("Detective nodes collect repository evidence.")
        st.write("Judge nodes generate independent opinions.")
        st.write("Chief Justice synthesizes final report and verdict.")

    return latest_state


def _list_history_reports() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def _render_run_tab() -> None:
    hero_left, hero_center, hero_right = st.columns([1, 2, 1])
    with hero_center:
        st.markdown("## LangGraph Automaton Auditor")
        st.caption("Run a forensic audit and review judicial outcomes in one dashboard.")

        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/owner/repo",
            key="run_repo_url",
        )
        start_audit = st.button("Start Audit", type="primary", use_container_width=True)

    if not start_audit:
        return

    if not repo_url.strip():
        st.warning("Please provide a GitHub repository URL.")
        return

    initial_state = _build_initial_state(repo_url)

    st.subheader("Live Swarm Status")
    status_col, logs_col = st.columns([2, 1])
    final_state = _run_audit_with_live_updates(initial_state, status_col, logs_col)

    overall_score = final_state.get("overall_score")
    try:
        overall_score_value = float(overall_score)
    except Exception:
        overall_score_value = 0.0

    st.subheader("Judicial Scorecard")
    score_col, chart_col = st.columns([1, 2])
    with score_col:
        st.metric("Overall Score", f"{overall_score_value:.1f}/5")
        st.metric("Verdict", str(final_state.get("audit_verdict", "N/A")))

    with chart_col:
        judge_scores = _get_judge_scores(final_state)
        judge_df = pd.DataFrame(
            {
                "Judge": list(judge_scores.keys()),
                "Score": list(judge_scores.values()),
            }
        ).set_index("Judge")
        st.bar_chart(judge_df)

    st.subheader("Final Audit Report")
    report_md = _render_markdown_report(final_state)
    with st.container(border=True):
        st.markdown(report_md)

    final_report_path = final_state.get("final_report_path")
    if final_report_path:
        st.caption(f"Saved report path: {final_report_path}")


def _render_history_tab() -> None:
    st.subheader("Audit History")
    reports = _list_history_reports()

    if not reports:
        st.info("No saved audit reports found in audit/report_onself_generated/.")
        return

    history_df = pd.DataFrame(
        {
            "Report File": [report.name for report in reports],
            "Last Updated": [
                report.stat().st_mtime for report in reports
            ],
        }
    )
    history_df["Last Updated"] = pd.to_datetime(history_df["Last Updated"], unit="s")
    st.dataframe(history_df, use_container_width=True, hide_index=True)

    selected_name = st.selectbox("Select a report to view", [report.name for report in reports], key="history_select")
    selected_report = REPORTS_DIR / selected_name

    if selected_report.exists():
        st.markdown(f"### {selected_report.name}")
        with st.container(border=True):
            st.markdown(selected_report.read_text(encoding="utf-8"))


st.markdown("# Automaton Auditor Executive Dashboard")
st.caption("Professional forensic auditing for LangGraph repositories.")

run_tab, history_tab = st.tabs(["Run New Audit", "Audit History"])

with run_tab:
    _render_run_tab()

with history_tab:
    _render_history_tab()
