import os
import tempfile
import ast
from typing import Any

import git

# 1. SANDBOXED CLONE
def clone_peer_repo(repo_url: str) -> str:
    if not repo_url or not repo_url.strip():
        return "Error: Repository URL is empty."

    temp_dir = tempfile.mkdtemp(prefix="peer_repo_")

    try:
        git.Repo.clone_from(repo_url.strip(), temp_dir)
        return os.path.abspath(temp_dir)
    except git.exc.GitCommandError:
        return (
            "Error: Failed to clone repository. The URL may be invalid, "
            "the repository may be private, or access credentials are missing."
        )
    except Exception as exc:
        return f"Error: Unexpected failure while cloning repository: {exc}"

# 2. GIT LOG EXTRACTION
def get_commit_metadata(repo_path: str) -> dict[str, Any]:
    try:
        repo = git.Repo(repo_path)
        total_commits = sum(1 for _ in repo.iter_commits())
        latest_commits = list(repo.iter_commits(max_count=3))
        latest_messages = [commit.message.strip() for commit in latest_commits]

        return {
            "total_commits": total_commits,
            "last_3_commit_messages": latest_messages,
        }
    except Exception as exc:
        return {
            "total_commits": 0,
            "last_3_commit_messages": [],
            "error": f"Unable to read commit metadata: {exc}",
        }


def _is_stategraph_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False

    function_node = node.func

    if isinstance(function_node, ast.Name):
        return function_node.id == "StateGraph"

    if isinstance(function_node, ast.Attribute):
        return function_node.attr == "StateGraph"

    return False

# 3. AST-BASED GRAPH ANALYSIS

def verify_langgraph_usage(file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        tree = ast.parse(source, filename=file_path)
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, SyntaxError):
        return False

    # FIX: This loop must be aligned with the 'try' block, not the 'except'
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_stategraph_call(node.value):
            return True
        if isinstance(node, ast.AnnAssign) and node.value and _is_stategraph_call(node.value):
            return True

    return False