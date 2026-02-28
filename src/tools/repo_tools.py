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
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url.strip(), temp_dir],
            capture_output=True,
            text=True,
            timeout=30,  # Explicit safety timeout
            shell=False,
            check=True,
        )

        return temp_dir
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(temp_dir)
        return f"Error: Git clone failed. {(exc.stderr or '').strip() or str(exc)}"
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


def _is_annotated_operator_add(node: ast.Subscript) -> bool:
    value_node = node.value
    if isinstance(value_node, ast.Name):
        is_annotated = value_node.id == "Annotated"
    elif isinstance(value_node, ast.Attribute):
        is_annotated = value_node.attr == "Annotated"
    else:
        is_annotated = False

    if not is_annotated:
        return False

    slice_node = node.slice
    tuple_values = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
    for value in tuple_values:
        if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
            if value.value.id == "operator" and value.attr == "add":
                return True
    return False


def analyze_graph_state_contract(repo_path: str) -> dict[str, Any]:
    graph_file = Path(repo_path) / "src" / "graph.py"
    state_file = Path(repo_path) / "src" / "state.py"

    result: dict[str, Any] = {
        "graph_file": str(graph_file),
        "state_file": str(state_file),
        "builder_variables": [],
        "add_node_count": 0,
        "add_edge_count": 0,
        "add_node_lines": [],
        "add_edge_lines": [],
        "has_annotated_operator_add": False,
        "stategraph_builder_detected": False,
        "graph_structure_verified": False,
        "summary": "",
    }

    try:
        graph_source = graph_file.read_text(encoding="utf-8")
        graph_tree = ast.parse(graph_source, filename=str(graph_file))
    except Exception as exc:
        result["summary"] = f"Graph AST parse failed: {exc}"
        return result

    builder_variables: set[str] = set()
    for node in ast.walk(graph_tree):
        if isinstance(node, ast.Assign) and _is_stategraph_call(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    builder_variables.add(target.id)
        elif isinstance(node, ast.AnnAssign) and node.value and _is_stategraph_call(node.value):
            target = node.target
            if isinstance(target, ast.Name):
                builder_variables.add(target.id)

    if builder_variables:
        result["stategraph_builder_detected"] = True
    result["builder_variables"] = sorted(builder_variables)

    allowed_receivers = set(builder_variables)
    allowed_receivers.add("builder")

    for node in ast.walk(graph_tree):
        if not isinstance(node, ast.Call):
            continue
        function_node = node.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if not isinstance(function_node.value, ast.Name):
            continue
        if function_node.value.id not in allowed_receivers:
            continue

        if function_node.attr == "add_node":
            result["add_node_count"] += 1
            result["add_node_lines"].append(getattr(node, "lineno", -1))
        elif function_node.attr == "add_edge":
            result["add_edge_count"] += 1
            result["add_edge_lines"].append(getattr(node, "lineno", -1))

    try:
        state_source = state_file.read_text(encoding="utf-8")
        state_tree = ast.parse(state_source, filename=str(state_file))
        for node in ast.walk(state_tree):
            if isinstance(node, ast.Subscript) and _is_annotated_operator_add(node):
                result["has_annotated_operator_add"] = True
                break
    except Exception:
        result["has_annotated_operator_add"] = False

    result["graph_structure_verified"] = bool(
        result["stategraph_builder_detected"]
        and result["add_node_count"] > 0
        and result["add_edge_count"] > 0
        and result["has_annotated_operator_add"]
    )

    result["summary"] = (
        "AST contract check: "
        f"builders={result['builder_variables']}, "
        f"add_node={result['add_node_count']}, "
        f"add_edge={result['add_edge_count']}, "
        f"annotated_operator_add={result['has_annotated_operator_add']}"
    )

    return result