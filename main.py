import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.graph import graph


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
    except Exception as exc:
        print(f"Rubric load warning: {exc}")
        return [], {}

def print_startup_env_checks() -> None:
    """Verifies that the required environment variables are present before execution."""
    api_key_detected = bool((os.getenv("LANGCHAIN_API_KEY") or "").strip())
    project_value = (os.getenv("LANGCHAIN_PROJECT") or "").strip()
    project_matches = project_value == "Auditor-Project-Week2"

    print("--- ENVIRONMENT CHECK ---")
    print(f"LANGCHAIN_API_KEY detected: {'Yes' if api_key_detected else 'No'}")
    print(
        "LANGCHAIN_PROJECT matches 'Auditor-Project-Week2': "
        f"{'Yes' if project_matches else 'No'}"
    )
    print("-------------------------")


def _extract_github_username(repo_url: str) -> str:
    cleaned = (repo_url or "").strip().rstrip("/")
    marker = "github.com/"
    username = "unknown_user"

    if marker in cleaned:
        tail = cleaned.split(marker, 1)[1]
        username = tail.split("/", 1)[0] if tail else "unknown_user"

    safe_username = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in username)
    return safe_username or "unknown_user"


def _save_unique_report(final_report, repo_url: str) -> str | None:
    os.makedirs("audit/report_onself_generated", exist_ok=True)
    os.makedirs("result", exist_ok=True)

    if final_report is None:
        return None

    if isinstance(final_report, dict):
        report_payload = final_report
    else:
        report_payload = final_report.model_dump() if hasattr(final_report, "model_dump") else {}

    if not isinstance(report_payload, dict) or not report_payload:
        return None

    username = _extract_github_username(repo_url)
    report_path = os.path.join("audit", "report_onself_generated", f"audit_report_{username}.md")

    executive_summary = str(report_payload.get("executive_summary") or "No executive summary available.")
    overall_score = report_payload.get("overall_score", "N/A")
    criteria = report_payload.get("criteria") or []
    remediation_plan = str(report_payload.get("remediation_plan") or "No remediation plan provided.")

    lines = [
        "# Audit Results",
        "",
        f"- **Repository:** {report_payload.get('repo_url', repo_url)}",
        f"- **Overall Score:** {overall_score}/5",
        "",
        "## Executive Summary",
        executive_summary,
        "",
        "## Criterion Breakdown",
    ]

    for criterion in criteria:
        if isinstance(criterion, dict):
            dimension_name = criterion.get("dimension_name") or criterion.get("dimension_id") or "Unknown"
            dimension_id = criterion.get("dimension_id") or "unknown"
            final_score = criterion.get("final_score", "N/A")
            dissent_summary = criterion.get("dissent_summary") or "No significant dissent detected."
            remediation = criterion.get("remediation") or "No remediation provided."
            judge_opinions = criterion.get("judge_opinions") or []
        else:
            dimension_name = getattr(criterion, "dimension_name", None) or getattr(criterion, "dimension_id", "Unknown")
            dimension_id = getattr(criterion, "dimension_id", "unknown")
            final_score = getattr(criterion, "final_score", "N/A")
            dissent_summary = getattr(criterion, "dissent_summary", None) or "No significant dissent detected."
            remediation = getattr(criterion, "remediation", None) or "No remediation provided."
            judge_opinions = getattr(criterion, "judge_opinions", []) or []

        lines.extend(
            [
                "",
                f"### {dimension_name} ({dimension_id})",
                "#### Final Score",
                f"{final_score}/5",
                "#### Dissent Summary",
                f"{dissent_summary}",
                "#### Remediation",
                f"{remediation}",
                "#### Judge Opinions",
            ]
        )

        for opinion in judge_opinions:
            if isinstance(opinion, dict):
                judge = opinion.get("judge", "Unknown")
                score = opinion.get("score", "N/A")
                argument = opinion.get("argument", "")
            else:
                judge = getattr(opinion, "judge", "Unknown")
                score = getattr(opinion, "score", "N/A")
                argument = getattr(opinion, "argument", "")
            lines.append(f"  - {judge}: score={score}, argument={argument}")

    lines.extend(["", "## Remediation Plan", remediation_plan, ""])
    report_content = "\n".join(lines)

    with open(report_path, "w", encoding="utf-8") as report_file:
        report_file.write(report_content)

    with open(os.path.join("result", "audit_result.md"), "w", encoding="utf-8") as latest_report_file:
        latest_report_file.write(report_content)

    return report_path

def run_audit(url: str):
    """Initializes and executes the forensic graph once, streaming progress and capturing results."""
    print(f"--- Starting Forensic Audit: {url} ---")
    rubric_dimensions, synthesis_rules = _load_rubric()
    
    initial_state = {
        "repo_url": url,
        "repo_path": None,
        "rubric_dimensions": rubric_dimensions,
        "synthesis_rules": synthesis_rules,
        "evidences": {},
        "opinions": [],
        "final_report": None,
        "audit_completed": False
    }
    
    print("Graph execution started...")
    
    # We create a variable to hold the 'latest' version of the state
    latest_state = initial_state

    # Run the Graph ONCE via stream
    for output in graph.stream(initial_state, stream_mode="updates"):
        for node_name, state_update in output.items():
            print(f"  [Node Completed]: {node_name}")
            # We merge the update into our latest_state tracking
            # This ensures we have the final data when the loop ends
            latest_state.update(state_update)

    print("\n--- JUDICIAL VERDICT ---")
    final_report = latest_state.get("final_report")

    if isinstance(final_report, dict):
        overall_score = final_report.get("overall_score")
        executive_summary = str(final_report.get("executive_summary") or "").strip()
        criteria = final_report.get("criteria") or []
    elif final_report is not None:
        overall_score = getattr(final_report, "overall_score", None)
        executive_summary = str(getattr(final_report, "executive_summary", "") or "").strip()
        criteria = getattr(final_report, "criteria", []) or []
    else:
        overall_score = None
        executive_summary = ""
        criteria = []

    if overall_score is not None:
        print(f"Overall Score: {overall_score}/5")
        verdict = "PASS" if float(overall_score) >= 3.5 else "FAIL"
        print(f"Verdict: {verdict}")
    else:
        print("Overall Score: Not available")
        print("Verdict: Not available")

    print("Executive Summary:")
    print(executive_summary if executive_summary else "No final report summary returned.")

    if criteria:
        print("\nDimension Results:")
        for criterion in criteria:
            if isinstance(criterion, dict):
                dimension_name = criterion.get("dimension_name") or criterion.get("dimension_id") or "Unknown"
                final_score = criterion.get("final_score", "N/A")
                dissent = criterion.get("dissent_summary")
            else:
                dimension_name = getattr(criterion, "dimension_name", None) or getattr(criterion, "dimension_id", "Unknown")
                final_score = getattr(criterion, "final_score", "N/A")
                dissent = getattr(criterion, "dissent_summary", None)
            print(f"- {dimension_name}: {final_score}/5")
            if dissent:
                print(f"  Dissent: {dissent}")
    else:
        print("No per-dimension results available.")

    unique_report_path = _save_unique_report(final_report, url)
    if unique_report_path:
        print(f"Audit Report Path: {unique_report_path}")
    else:
        print("Audit Report Path: Not generated (final report unavailable).")

    # Now we use 'latest_state' instead of calling graph.invoke()
    print("\n--- FINAL AUDIT EVIDENCE ---")
    
    evidences = latest_state.get("evidences", {})

    if not evidences:
        print("No evidence collected. Check if the repository URL is valid.")
    else:
        for dimension_id, evidence_list in evidences.items():
            print(f"[{dimension_id}]")
            for ev in evidence_list:
                goal = getattr(ev, "goal", "Unknown goal")
                found = getattr(ev, "found", False)
                rationale = getattr(ev, "rationale", "No rationale provided")
                confidence = getattr(ev, "confidence", 0.0)
                status = "✅ FOUND" if found else "❌ NOT FOUND"
                print(f"  {status} {goal}")
                print(f"    Rationale: {rationale}")
                print(f"    Confidence: {int(float(confidence) * 100)}%\n")

    if unique_report_path:
        print(
            "Self-audit report saved to audit/report_onself_generated/ and mirrored to result/audit_result.md"
        )
    else:
        print("--- AUDIT COMPLETE: No unique report file was saved. ---")

        
# For Test by inputting the URL directly to the terminal  

# if __name__ == "__main__":
#     print_startup_env_checks()

#     # STEP 3 UPGRADE: Command Line Argument Support
#     # Usage: uv run main.py https://github.com/user/repo
#     if len(sys.argv) > 1:
#         target_url = sys.argv[1]
#     else:
#         # Fallback to default for quick testing if no arg provided
#         target_url = "https://github.com/langchain-ai/langgraph-example"
#         print(f"No URL provided. Using default: {target_url}")

#     run_audit(target_url)



# For Test By editing the URL here 

if __name__ == "__main__":
    print_startup_env_checks()

    # --- EDIT THIS URL FOR TESTING ---
    # Just paste the repo you want to test here

    test_repo = "https://github.com/langchain-ai/langgraph-example" 
    # test_repo = "https://github.com/yakobd/Netflix-clone.git"

    # Logic: Use command line arg if provided, otherwise use the test_repo above
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        target_url = test_repo
        print(f"Using Hardcoded Test URL: {target_url}")

    run_audit(target_url)