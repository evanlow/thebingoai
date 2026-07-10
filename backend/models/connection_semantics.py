"""ConnectionSemanticLayer — human-curated meaning for a connection's data.

One row per DatabaseConnection, holding three JSONB sections:

- ``glossary``      — per-column display names, descriptions, and a ``sensitive``
                      flag: ``{"<table>.<column>": {...}}`` (also table-level keys)
- ``relationships`` — human-confirmed / rejected / data-detected join edges
- ``definitions``   — named business metrics (name + description + SQL fragment)

Stored SEPARATELY from ``database_connections.data_context`` because that column
is fully rebuilt on every profiling run — edits kept here survive re-profiling
and are overlaid at read time by ``services.semantic_layer.merge_semantics_into_context``.
"""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database.base import Base, TimestampMixin


class ConnectionSemanticLayer(Base, TimestampMixin):
    __tablename__ = "connection_semantic_layers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(
        Integer,
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    glossary = Column(JSONB, nullable=False, default=dict, server_default="{}")
    relationships_data = Column(
        "relationships", JSONB, nullable=False, default=list, server_default="[]"
    )
    definitions = Column(JSONB, nullable=False, default=list, server_default="[]")

    connection = relationship("DatabaseConnection")
