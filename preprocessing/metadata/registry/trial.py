"""Codebook fields for the trial view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="trial.trial_id",
        view_level="trial",
        variable_name="trial_id",
        feature_label="Trial identifier",
        description="Trial identifier inside the session",
        data_type="string",
        source_section="experiment_procedure",
        pipeline_field="trial_id",
        yaml_path="trials[].trial_id",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="View key for the trial level",
    ),
)
