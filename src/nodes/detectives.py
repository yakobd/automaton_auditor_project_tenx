import ast
import subprocess
from pathlib import Path

from src.state import AgentState, Evidence
from src.tools.doc_tools import analyze_repo_pdf
from src.tools.repo_tools import clone_peer_repo, get_commit_metadata


def _evidence(
    goal: str,
    found: bool,
    content: str,
    location: str,
    rationale: str,
    confidence: float,
) -> Evidence:
    return Evidence(
        goal=goal,
        found=found,
        content=content,
        location=location,
        rationale=rationale,
        confidence=confidence,
    )


def _normalize_doc_evidence(raw: object, repo_path: str) -> Evidence:
    if isinstance(raw, Evidence):
        return raw

    goal = str(getattr(raw, "goal", "Documentation coverage and technical indicators"))
    found = bool(getattr(raw, "found", False))
    content = str(
        getattr(raw, "content", None)
        or getattr(raw, "summary", "No documentation details were provided by analyzer.")
    )
    location = str(getattr(raw, "location", repo_path))
    rationale = str(
        getattr(raw, "rationale", "Evaluated repository PDF documentation for required technical indicators.")
    )
    confidence = getattr(raw, "confidence", 0.85)
    try:
        confidence_value = float(confidence)
    except Exception:
        confidence_value = 0.85
    confidence_value = max(0.0, min(1.0, confidence_value))

    return _evidence(
        goal=goal,
        found=found,
        content=content,
        location=location,
        rationale=rationale,
        confidence=confidence_value,
    )


def _collect_forensic_queries(
    rubric_dimensions: list,
    target_artifacts: set[str],
    fallback_queries: list[str],
) -> list[str]:
    queries: list[str] = []
    for dimension in rubric_dimensions:
        if not isinstance(dimension, dict):
            continue

        artifact = str(dimension.get("target_artifact", "")).strip().lower()
        if artifact and artifact not in target_artifacts:
            continue

        forensic_instruction = str(dimension.get("forensic_instruction", "")).strip()
        if forensic_instruction:
            queries.append(forensic_instruction)

        for key in ("id", "name", "success_pattern", "failure_pattern"):
            value = str(dimension.get(key, "")).strip()
            if value:
                queries.append(value)

    return queries or fallback_queries


def analyze_graph_structure(file_path: str) -> tuple[bool, str]:
    """Parse Python source with AST and detect real StateGraph instantiation calls."""
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return False, f"Forensic Error: SyntaxError in {file_path}: {exc.msg} (line {exc.lineno})."
    except UnicodeDecodeError as exc:
        return False, f"Forensic Error: UnicodeDecodeError in {file_path}: {exc}."
    except (FileNotFoundError, PermissionError) as exc:
        return False, f"Forensic Error: Unable to access {file_path}: {exc}."
    except Exception as exc:
        return False, f"Forensic Error: Unexpected AST failure in {file_path}: {exc}."

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        function_node = node.func
        if isinstance(function_node, ast.Name) and function_node.id == "StateGraph":
            return True, "StateGraph() call detected via AST."
        if isinstance(function_node, ast.Attribute) and function_node.attr == "StateGraph":
            return True, "StateGraph() call detected via AST."

    return False, "No StateGraph() instantiation call found via AST."


def extract_git_history(path: str) -> tuple[list[str], str]:
    """Extract recent commit history using git log for atomic progress assessment."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--max-count", "12"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return [], f"Git log extraction failed: {stderr or str(exc)}"
    except Exception as exc:
        return [], f"Git log extraction failed: {exc}"

    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if not lines:
        return [], "No commit history returned by git log."

    return lines, "ok"


def repo_investigator_node(state: AgentState):
    repo_path = state.get("repo_path")
    repo_url = state.get("repo_url", "")

    if repo_path:
        cloned_path = repo_path
    elif not repo_url:
        return {
            "evidences": {
                "langgraph_usage": [
                    _evidence(
                        goal="Presence of LangGraph StateGraph implementation",
                        found=False,
                        content="Repository URL missing; cannot inspect source.",
                        location="state.repo_url",
                        rationale="Audit is blocked without a valid repository target.",
                        confidence=1.0,
                    )
                ],
                "atomic_progress": [
                    _evidence(
                        goal="Sufficient atomic commit progress (>=3 commits)",
                        found=False,
                        content="Repository URL missing; cannot inspect git history.",
                        location="state.repo_url",
                        rationale="Commit history cannot be evaluated without cloning a repository.",
                        confidence=1.0,
                    )
                ],
            },
            "repo_path": "",
        }
    else:
        cloned_path = clone_peer_repo(repo_url)

    if isinstance(cloned_path, str) and cloned_path.startswith("Error:"):
        return {
            "evidences": {
                "langgraph_usage": [
                    _evidence(
                        goal="Presence of LangGraph StateGraph implementation",
                        found=False,
                        content=f"Clone failed: {cloned_path}",
                        location=repo_url or "unknown",
                        rationale="Source code analysis cannot proceed when clone operation fails.",
                        confidence=1.0,
                    )
                ],
                "atomic_progress": [
                    _evidence(
                        goal="Sufficient atomic commit progress (>=3 commits)",
                        found=False,
                        content="Clone failed; commit metadata unavailable.",
                        location=repo_url or "unknown",
                        rationale="Git metadata extraction depends on a successful clone path.",
                        confidence=1.0,
                    )
                ],
            },
            "repo_path": "",
        }

    repo_root = Path(cloned_path)

    large_files = [
        str(file_path.relative_to(repo_root))
        for file_path in repo_root.rglob("*")
        if file_path.is_file() and file_path.stat().st_size > 5 * 1024 * 1024
    ]
    hygiene_ok = len(large_files) == 0

    forbidden_files = {".env", "secrets.json", "id_rsa"}
    leaked = [
        str(file_path.relative_to(repo_root))
        for file_path in repo_root.rglob("*")
        if file_path.name in forbidden_files
    ]
    secrets_ok = len(leaked) == 0

    python_files = list(repo_root.rglob("*.py"))
    has_formal_graph = False
    forensic_errors: list[str] = []
    for file_path in python_files:
        is_found, message = analyze_graph_structure(str(file_path))
        if is_found:
            has_formal_graph = True
            break
        if "Forensic Error" in message:
            forensic_errors.append(message)

    metadata = get_commit_metadata(cloned_path)
    total_commits = int(metadata.get("total_commits", 0))
    git_history, git_history_status = extract_git_history(cloned_path)

    recent_messages = [entry.split(" ", 1)[1].strip().lower() if " " in entry else entry.lower() for entry in git_history]
    has_one_big_initial_commit = total_commits <= 1 and any("initial commit" in message for message in recent_messages)
    atomic_progress_ok = total_commits >= 3 and not has_one_big_initial_commit

    if has_one_big_initial_commit:
        atomic_assessment = (
            f"Total commits detected: {total_commits}. FAIL: single 'initial commit' pattern detected, "
            "indicating non-incremental development."
        )
    elif atomic_progress_ok:
        atomic_assessment = f"Total commits detected: {total_commits}. Incremental commit history appears healthy."
    else:
        atomic_assessment = (
            f"Total commits detected: {total_commits}. Commit history appears sparse; incremental progress not established."
        )

    if git_history:
        history_excerpt = "\n".join(f"- {line}" for line in git_history[:8])
        atomic_assessment += f"\nRecent git log entries:\n{history_excerpt}"
    elif git_history_status != "ok":
        atomic_assessment += f"\nGit history status: {git_history_status}"

    langgraph_content = "StateGraph detected." if has_formal_graph else "No StateGraph detected."
    if forensic_errors:
        langgraph_content += f" Parser forensic errors: {len(forensic_errors)}"

    return {
        "evidences": {
            "langgraph_usage": [
                _evidence(
                    goal="Presence of LangGraph StateGraph implementation",
                    found=has_formal_graph,
                    content=langgraph_content,
                    location=str(repo_root),
                    rationale="AST verification checks for explicit LangGraph StateGraph construction.",
                    confidence=0.95,
                )
            ],
            "atomic_progress": [
                _evidence(
                    goal="Sufficient atomic commit progress (>=3 commits)",
                    found=atomic_progress_ok,
                    content=atomic_assessment,
                    location=str(repo_root / ".git"),
                    rationale="Uses git log commit history to verify incremental commits and flag single big initial-commit patterns.",
                    confidence=1.0,
                )
            ],
            "repository_hygiene": [
                _evidence(
                    goal="Repository free from oversized binaries (>5MB)",
                    found=hygiene_ok,
                    content=(
                        "No oversized binaries detected."
                        if hygiene_ok
                        else f"Oversized files detected: {large_files}"
                    ),
                    location=str(repo_root),
                    rationale="Large binary files reduce repository hygiene and complicate source control workflows.",
                    confidence=0.9,
                )
            ],
            "security_hardening": [
                _evidence(
                    goal="No leaked secret files (.env, secrets.json, id_rsa)",
                    found=secrets_ok,
                    content=(
                        "No leaked secret artifacts detected."
                        if secrets_ok
                        else f"Leaked secret artifacts detected: {leaked}"
                    ),
                    location=str(repo_root),
                    rationale="Presence of committed secret artifacts is a direct security vulnerability signal.",
                    confidence=1.0,
                )
            ],
        },
        "repo_path": str(repo_root),
    }


def doc_analyst_node(state: AgentState):
    repo_path = state.get("repo_path", "")
    rubric_dimensions = state.get("rubric_dimensions", [])

    rubric_queries = _collect_forensic_queries(
        rubric_dimensions=rubric_dimensions,
        target_artifacts={"pdf_report", "pdf_images"},
        fallback_queries=["graph", "state", "reducers", "langgraph"],
    )

    if not repo_path:
        return {
            "evidences": {
                "documentation_coverage": [
                    _evidence(
                        goal="Documentation contains required technical indicators",
                        found=False,
                        content="Repository path missing; documentation analysis blocked.",
                        location="state.repo_path",
                        rationale="Doc analysis requires a valid local repository path.",
                        confidence=1.0,
                    )
                ]
            }
        }

    try:
        raw_doc_evidence = analyze_repo_pdf(repo_path, rubric_queries=rubric_queries)
        doc_evidence = _normalize_doc_evidence(raw_doc_evidence, repo_path)
    except Exception as exc:
        doc_evidence = _evidence(
            goal="Documentation contains required technical indicators",
            found=False,
            content=f"Documentation analyzer failed: {exc}",
            location=repo_path,
            rationale="Analyzer failure prevents reliable extraction of documentation evidence.",
            confidence=1.0,
        )

    return {"evidences": {"documentation_coverage": [doc_evidence]}}
