"""Codebook fields for the session view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="session.session_identifier",
        view_level="session",
        variable_name="session_identifier",
        feature_label="Session identifier",
        description="Session identifier",
        data_type="string",
        source_section="administrative",
        pipeline_field="session_identifier",
        yaml_path="administrative.session_identifier",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="View key for the session level",
    ),
)
