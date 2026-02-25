import operator
from typing import Annotated, TypedDict, List, Optional

from pydantic import BaseModel, Field

class Evidence(BaseModel):
    title: str
    severity: int = Field(ge=1, le=5)
    summary: str
    source: str

# ADD THIS: To satisfy the JudicialOpinion requirement
class JudicialOpinion(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    recommendation: str

class AgentState(TypedDict):
    # Proper reducer (operator.add) as required
    evidences: Annotated[List[Evidence], operator.add]
    # Optional: Adding JudicialOpinion to your state
    opinion: Optional[JudicialOpinion] 
    repo_url: str
    repo_path: Optional[str] = None
    audit_completed: bool = False