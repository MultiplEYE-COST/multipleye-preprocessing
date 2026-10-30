"""Codebook fields for the dataset view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="dataset.data_collection_name",
        view_level="dataset",
        variable_name="data_collection_name",
        feature_label="Name of data collection",
        description="Name of the data collection",
        data_type="string",
        source_section="administrative",
        pipeline_field="data_collection_name",
        yaml_path="administrative.title",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="View key for the dataset level",
    ),
)
