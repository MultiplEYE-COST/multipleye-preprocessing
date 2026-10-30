"""Codebook fields for the item view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="item.text_id",
        view_level="item",
        variable_name="text_id",
        feature_label="Item ID",
        description="Language specific stimulus text identifier",
        data_type="string",
        source_section="stimuli",
        pipeline_field="text_id",
        yaml_path="items[].text_id",
        semantic_category="stimulus",
        aggregation_behavior="not_applicable",
        notes="View key for the item level",
    ),
)
