"""Request/response schemas for the per-connection semantic layer."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SemanticLayerResponse(BaseModel):
    glossary: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)
    definitions: List[Dict[str, Any]] = Field(default_factory=list)


class SemanticLayerUpdate(BaseModel):
    """Section-level replace — only sections provided (non-null) are written."""
    glossary: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    definitions: Optional[List[Dict[str, Any]]] = None
