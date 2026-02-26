import os
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from src.state import AgentState


class JudicialOpinion(BaseModel):
    score: int = Field(ge=1, le=5)
    argument: str = Field(min_length=1)
    cited_evidence: list[str] = Field(default_factory=list)


def _format_evidence_block(state: AgentState) -> str:
    evidences = state.get("evidences", [])
    if not evidences:
        return "No evidences were collected. Treat this as a severe audit-quality failure."

    lines: list[str] = []
    for idx, evidence in enumerate(evidences, start=1):
        title = getattr(evidence, "title", "Untitled")
        severity = getattr(evidence, "severity", "N/A")
        source = getattr(evidence, "source", "Unknown")
        summary = getattr(evidence, "summary", "")
        rationale = getattr(evidence, "rationale", "")
        confidence = getattr(evidence, "confidence", "N/A")
        lines.append(
            f"{idx}. Title: {title}\n"
            f"   Severity: {severity}\n"
            f"   Source: {source}\n"
            f"   Summary: {summary}\n"
            f"   Rationale: {rationale}\n"
            f"   Confidence: {confidence}"
        )

    return "\n".join(lines)


def _invoke_structured_opinion(system_prompt: str, user_prompt: str, temperature: float, max_retries: int = 3) -> JudicialOpinion | None:
    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        groq_api_key=os.getenv('GROQ_API_KEY'),
    ).with_structured_output(JudicialOpinion)

    for _ in range(max_retries):
        try:
            time.sleep(2)
            result = model.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            if isinstance(result, JudicialOpinion) and result.argument.strip() and result.cited_evidence:
                return result
        except Exception:
            continue

    return None


def _format_structured_output(opinion: JudicialOpinion) -> str:
    cited_lines = "\n".join(f"- {item}" for item in opinion.cited_evidence)
    return (
        f"Score (1-5): {opinion.score}\n"
        f"Argument: {opinion.argument}\n"
        f"Cited Evidence:\n{cited_lines}"
    )


def prosecutor_node(state: AgentState):
    """Generate a skeptical prosecutor-style critique from collected evidences."""
    evidence_block = _format_evidence_block(state)
    repo_url = state.get("repo_url", "Unknown repository")

    system_prompt = (
        "You are a skeptical senior software auditor acting as a prosecutor. "
        "Return ONLY a structured JudicialOpinion object with fields: "
        "score (1-5), argument (string), and cited_evidence (list of strings). "
        "Do not invent facts; cite only provided evidence."
    )

    user_prompt = (
        f"Repository under audit: {repo_url}\n\n"
        "Collected evidence:\n"
        f"{evidence_block}\n\n"
        "Produce a harsh prosecution argument focused on reliability, security, and process risk."
    )

    opinion = _invoke_structured_opinion(system_prompt, user_prompt, temperature=0.2)
    if opinion is None:
        opinion = JudicialOpinion(
            score=3,
            argument="Structured prosecutor output unavailable after retries; audit risk remains unresolved.",
            cited_evidence=["LLM failed to return valid structured output after retries."],
        )

    critique = _format_structured_output(opinion)
    return {
        "prosecutor_critique": critique,
        "metadata": {"prosecutor_structured": opinion.model_dump()},
    }
