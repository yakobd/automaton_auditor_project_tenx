import os

from dotenv import load_dotenv
load_dotenv()  # This looks for the .env file and loads the variables

from src.graph import graph


def print_startup_env_checks() -> None:
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
    print(f"--- Starting Audit for: {url} ---")
    
    # Initialize the state
    initial_state = {
        "repo_url": url,
        "evidences": []
    }
    
    # Run the Graph
    final_state = graph.invoke(initial_state)
    
    # Print the Results
    print("\n--- FINAL AUDIT EVIDENCE ---")
    for ev in final_state["evidences"]:
        status = "❌ CRITICAL" if ev.severity >= 4 else "✅ PASS"
        print(f"[{status}] {ev.title} ({ev.source})")
        print(f"    Summary: {ev.summary}\n")

if __name__ == "__main__":
    print_startup_env_checks()

    # Test with the example repo again
    test_url = "https://github.com/langchain-ai/langgraph-example"
    run_audit(test_url)