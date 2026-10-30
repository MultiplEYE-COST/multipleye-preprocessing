"""Codebook fields for the participant view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="participant.participant_id",
        view_level="participant",
        variable_name="participant_id",
        feature_label="Participant ID",
        description="Participant group identifier",
        data_type="string",
        source_section="administrative",
        pipeline_field="participant_id",
        yaml_path="participants[].participant_id",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="View key for the participant level",
    ),
)
