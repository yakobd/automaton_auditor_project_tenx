import os
import tempfile
import ast
import subprocess
import shutil
from pathlib import Path
from typing import Any

import git

# 1. SANDBOXED CLONE
import subprocess
import shutil
from pathlib import Path
import tempfile

def clone_peer_repo(repo_url: str) -> str:
    """
    Forensically isolated clone using a secure TemporaryDirectory.
    Includes explicit error handling and subprocess timeouts.
    """
    # Create a persistent-path-safe temp directory
    temp_dir = tempfile.mkdtemp(prefix="forensic_audit_")
    
    try:
        # Use subprocess for explicit return-code handling and security
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url.strip(), temp_dir],
            capture_output=True,
            text=True,
            timeout=30  # Explicit safety timeout
        )
        
        if result.returncode != 0:
            shutil.rmtree(temp_dir) # Clean up on failure
            return f"Error: Git clone failed. {result.stderr.strip()}"
            
        return temp_dir
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir)
        return "Error: Git clone timed out after 30 seconds."
    except Exception as e:
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
        return f"Error: Forensic sandbox failure: {str(e)}"
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

def verify_langgraph_usage(file_path: str) -> tuple[bool, str]:
    try:
        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return (
            False,
            f"Forensic Error: SyntaxError while parsing '{file_path}': {exc.msg} (line {exc.lineno}).",
        )
    except UnicodeDecodeError as exc:
        return (
            False,
            f"Forensic Error: UnicodeDecodeError while reading '{file_path}': {exc}.",
        )
    except (FileNotFoundError, PermissionError) as exc:
        return False, f"Forensic Error: Unable to access '{file_path}': {exc}."
    except Exception as exc:
        return False, f"Forensic Error: Unexpected analysis failure for '{file_path}': {exc}."

    # FIX: This loop must be aligned with the 'try' block, not the 'except'
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_stategraph_call(node.value):
            return True, "StateGraph assignment detected."
        if isinstance(node, ast.AnnAssign) and node.value and _is_stategraph_call(node.value):
            return True, "StateGraph assignment detected."

    return False, "No formal StateGraph assignment found."