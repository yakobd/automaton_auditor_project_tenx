from pathlib import Path

from src.tools.repo_tools import clone_peer_repo
from src.tools.repo_tools import get_commit_metadata, verify_langgraph_usage


def main() -> None:
	

	# Repo which is not well structured for test purpose 
	# repo_url = "https://github.com/yakobd/MyPortfolioWebsite.git"
	
    # well structured Repo for test purpose
	repo_url = "https://github.com/langchain-ai/langgraph-example"



	print(f"Cloning repository: {repo_url}")
	cloned_repo_path = clone_peer_repo(repo_url)
	print(f"Local clone path: {cloned_repo_path}")

	if cloned_repo_path.startswith("Error:"):
		print("Clone failed, skipping AST and commit metadata checks.")
		return

	repo_root = Path(cloned_repo_path)
	python_files = list(repo_root.rglob("*.py"))

	langgraph_matches: list[str] = []
	for python_file in python_files:
		if verify_langgraph_usage(str(python_file)):
			langgraph_matches.append(str(python_file))

	print("\nAST verification results")
	print(f"Python files scanned: {len(python_files)}")
	print(f"Files with StateGraph instantiation: {len(langgraph_matches)}")

	preview_limit = 10
	for match in langgraph_matches[:preview_limit]:
		print(f"- {match}")

	if len(langgraph_matches) > preview_limit:
		remaining = len(langgraph_matches) - preview_limit
		print(f"... and {remaining} more")

	metadata = get_commit_metadata(cloned_repo_path)
	print("\nCommit metadata (Atomic Progress)")
	print(f"Total commits: {metadata.get('total_commits', 0)}")

	for index, message in enumerate(metadata.get("last_3_commit_messages", []), start=1):
		print(f"{index}. {message}")

	if "error" in metadata:
		print(f"Metadata error: {metadata['error']}")


if __name__ == "__main__":
	main()
