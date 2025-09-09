from typing import Optional, List
from pydantic import BaseModel, Field, confloat

class RequirementOutput(BaseModel):
    req_id: Optional[str] = Field(None, description="Unique requirement identifier if present.")
    source_file: Optional[str] = Field(None, description="Source file URI or filename.")
    section: Optional[str] = Field(None, description="Nearest heading/section inferred from document.")
    text: str = Field(..., description="Canonical full requirement text.")
    acceptance_criteria: List[str] = Field(default_factory=list, description="...")
    priority: Optional[str] = Field(None, description="Inferred priority: 'P1','P2','P3'.")
    type: List[str] = Field(default_factory=list, description="Controlled vocabulary types.")
    tags: List[str] = Field(default_factory=list, description="Short kebab-case keywords.")
    referenced_standards: List[str] = Field(default_factory=list, description="...")
    page: Optional[int] = Field(None, description="Page number in source doc.")
    confidence: confloat(ge=0.0, le=1.0) = Field(0.0, description="Overall extraction confidence.")
    tags_confidence: confloat(ge=0.0, le=1.0) = Field(0.0, description="Tags/type confidence.")
    extraction_notes: Optional[str] = Field(None, description="Short notes about ambiguities.")