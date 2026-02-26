import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from src.graph import graph

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

def run_audit(url: str):
    """Initializes and executes the forensic graph once, streaming progress and capturing results."""
    print(f"--- Starting Forensic Audit: {url} ---")
    
    initial_state = {
        "repo_url": url,
        "evidences": [],
        "prosecutor_critique": "",
        "defense_counsel": "",
        "metadata": {},
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

    prosecutor_critique = (latest_state.get("prosecutor_critique") or "").strip()
    print("\n--- PROSECUTOR'S CRITIQUE ---")
    print(prosecutor_critique if prosecutor_critique else "No prosecutor critique generated.")

    defense_argument = (latest_state.get("defense_counsel") or "").strip()
    print("\n--- DEFENSE ARGUMENT ---")
    print(defense_argument if defense_argument else "No defense argument generated.")

    print("\n--- JUDICIAL VERDICT ---")
    opinion = latest_state.get("opinion")
    metadata = latest_state.get("metadata") or {}

    final_score = None
    judge_verdict = (latest_state.get("judge_verdict") or "").strip()
    judicial_opinion_text = (latest_state.get("judicial_opinion") or "").strip()

    if isinstance(opinion, dict):
        final_score = opinion.get("score")
        judge_verdict = judge_verdict or str(opinion.get("verdict") or "").strip()
        judicial_opinion_text = judicial_opinion_text or str(opinion.get("reasoning") or "").strip()
    elif opinion is not None:
        final_score = getattr(opinion, "score", None)
        judge_verdict = judge_verdict or str(getattr(opinion, "verdict", "") or "").strip()
        judicial_opinion_text = judicial_opinion_text or str(getattr(opinion, "reasoning", "") or "").strip()

    if final_score is not None:
        print(f"Final Score: {final_score}/100")
    else:
        print("Final Score: Not available")

    print(f"Verdict: {judge_verdict if judge_verdict else 'Not available'}")
    print("Judicial Opinion:")
    print(judicial_opinion_text if judicial_opinion_text else "No judicial explanation returned.")

    dissent_summary = (metadata.get("dissent_summary") or "").strip()
    if dissent_summary:
        print("Dissent Summary:")
        print(dissent_summary)

    audit_report_path = (metadata.get("audit_report_path") or "reports/audit_results.md").strip()
    print(f"Audit Report Path: {audit_report_path}")

    # Now we use 'latest_state' instead of calling graph.invoke()
    print("\n--- FINAL AUDIT EVIDENCE ---")
    
    evidences = latest_state.get("evidences", [])
    
    if not evidences:
        print("No evidence collected. Check if the repository URL is valid.")
    else:
        for ev in evidences:
            icon = "❌ CRITICAL" if ev.severity >= 4 else "⚠️ WARNING" if ev.severity == 3 else "✅ INFO"
            print(f"[{icon}] {ev.title} (Source: {ev.source})")
            print(f"    Rationale: {ev.summary}")
            print(f"    Confidence: {int(ev.confidence * 100)}%\n")

    print("--- AUDIT COMPLETE: Report saved to reports/audit_results.md ---")

        
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