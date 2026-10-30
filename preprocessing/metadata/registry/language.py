"""Codebook fields for the dataset language node metadata."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

FIELDS = (
    CodebookField(
        variable_id="dataset.language_node_id",
        view_level="dataset",
        variable_name="language_node_id",
        feature_label="Language node ID",
        description="Identifier of the selected node in the EyeStore language tree",
        data_type="string",
        source_section="language",
        pipeline_field="language_node_id",
        yaml_path="language_node.language_node_id",
        semantic_category="language",
        aggregation_behavior="static",
        notes=(
            "Configured per data collection. Separate from the ISO language code, "
            "country code and session identifier"
        ),
    ),
    CodebookField(
        variable_id="dataset.language_node_path",
        view_level="dataset",
        variable_name="language_node_path",
        feature_label="Language node path",
        description="Full path from the language tree root to the selected node",
        data_type="string",
        source_section="language",
        pipeline_field="language_node_path",
        yaml_path="language_node.language_node_path",
        semantic_category="language",
        aggregation_behavior="static",
        notes="Taken from the pinned tree snapshot when one is configured",
    ),
    CodebookField(
        variable_id="dataset.language_node_label",
        view_level="dataset",
        variable_name="language_node_label",
        feature_label="Language node label",
        description="Human readable label of the selected language node",
        data_type="string",
        source_section="language",
        pipeline_field="language_node_label",
        yaml_path="language_node.language_node_label",
        semantic_category="language",
        aggregation_behavior="static",
        notes="Available when the pinned tree snapshot is configured",
    ),
    CodebookField(
        variable_id="dataset.language_tree_version",
        view_level="dataset",
        variable_name="language_tree_version",
        feature_label="Language tree version",
        description="Version of the pinned EyeStore language tree snapshot",
        data_type="string",
        source_section="language",
        pipeline_field="language_tree_version",
        yaml_path="language_node.language_tree_version",
        semantic_category="language",
        aggregation_behavior="static",
    ),
    CodebookField(
        variable_id="dataset.language_tree_hash",
        view_level="dataset",
        variable_name="language_tree_hash",
        feature_label="Language tree hash",
        description="SHA256 hash of the pinned EyeStore language tree snapshot",
        data_type="string",
        source_section="language",
        pipeline_field="language_tree_hash",
        yaml_path="language_node.language_tree_hash",
        semantic_category="language",
        aggregation_behavior="static",
        notes="Identifies the exact tree content used for validation",
    ),
)
