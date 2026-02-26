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
        return "No evidences were provided."

    lines: list[str] = []
    for index, evidence in enumerate(evidences, start=1):
        title = getattr(evidence, "title", "Untitled")
        severity = getattr(evidence, "severity", "N/A")
        summary = getattr(evidence, "summary", "")
        source = getattr(evidence, "source", "Unknown")
        lines.append(
            f"{index}. {title} | severity={severity} | source={source} | summary={summary}"
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


def tech_lead_node(state: AgentState):
    """Generate a pragmatic tie-breaker assessment between prosecutor and defense."""
    prosecutor_critique = (state.get("prosecutor_critique") or "").strip()
    defense_counsel = (state.get("defense_counsel") or "").strip()
    evidence_block = _format_evidence_block(state)

    system_prompt = (
        "Persona: Pragmatic Tech Lead. "
        "Focus on architectural soundness, code cleanliness, and practical viability. "
        "You are the tie-breaker between the Prosecutor and Defense. "
        "Return ONLY a structured JudicialOpinion object with fields: "
        "score (1-5), argument (string), and cited_evidence (list of strings)."
    )

    user_prompt = (
        "Review the forensic evidence and both sides' arguments.\n"
        "Produce a tie-breaker judgment for the judge based on architecture, code quality, and delivery viability.\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        f"Prosecutor Critique:\n{prosecutor_critique or 'No prosecutor critique provided.'}\n\n"
        f"Defense Argument:\n{defense_counsel or 'No defense argument provided.'}"
    )

    opinion = _invoke_structured_opinion(system_prompt, user_prompt, temperature=0.2)
    if opinion is None:
        opinion = JudicialOpinion(
            score=3,
            argument="Structured tech lead output unavailable after retries; tie-breaker confidence is limited.",
            cited_evidence=["LLM failed to return valid structured output after retries."],
        )

    assessment = _format_structured_output(opinion)
    return {
        "metadata": {
            "tech_lead_assessment": assessment,
            "tech_lead_structured": opinion.model_dump(),
        }
    }
