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
    """Initializes and executes the forensic graph for a target repository."""
    print(f"--- Starting Forensic Audit: {url} ---")
    
    # Initialize the state as defined in src/state.py
    initial_state = {
        "repo_url": url,
        "evidences": [],
        "metadata": {},
        "audit_completed": False
    }
    
    # Run the Graph using stream to show progress/node execution
    # This addresses the 'tracing' and 'visibility' feedback
    print("Graph execution started...")
    final_output = None
    for output in graph.stream(initial_state):
        for node_name, state_update in output.items():
            print(f"  [Node Completed]: {node_name}")
            final_output = state_update # Keep track of the latest state

    # Extract final evidences from the combined graph state
    # We use invoke/get_state logic or pull from the last stream event
    final_state = graph.invoke(initial_state)
    
    # Print the Results in a formatted report
    print("\n--- FINAL AUDIT EVIDENCE ---")
    if not final_state.get("evidences"):
        print("No evidence collected. Check if the repository URL is valid.")
    else:
        for ev in final_state["evidences"]:
            # Severity 4-5 are critical, 3 is warning, 1-2 are info
            icon = "❌ CRITICAL" if ev.severity >= 4 else "⚠️ WARNING" if ev.severity == 3 else "✅ INFO"
            print(f"[{icon}] {ev.title} (Source: {ev.source})")
            print(f"    Rationale: {ev.summary}")
            print(f"    Confidence: {int(ev.confidence * 100)}%\n")

if __name__ == "__main__":
    print_startup_env_checks()

    # STEP 3 UPGRADE: Command Line Argument Support
    # Usage: uv run main.py https://github.com/user/repo
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    else:
        # Fallback to default for quick testing if no arg provided
        target_url = "https://github.com/langchain-ai/langgraph-example"
        print(f"No URL provided. Using default: {target_url}")

    run_audit(target_url)