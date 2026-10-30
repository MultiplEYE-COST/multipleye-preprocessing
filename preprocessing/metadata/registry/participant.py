"""Codebook fields for the participant view."""

from __future__ import annotations

from preprocessing.metadata.schema import CodebookField

__all__ = ["FIELDS"]

_PQ_NUMBER_FIELDS = {
    "pq_age",
    "pq_years_education",
    "pq_years_education_open_ended",
}

_PQ_FIELDS = (
    "pq_gender",
    "pq_age",
    "pq_years_education",
    "pq_years_education_open_ended",
    "pq_level_education",
    "pq_socio_economic_status",
    "pq_childhood_languages",
    "pq_tiredness",
    "pq_eyewear",
    "pq_alcohol_yesterday",
    "pq_alcohol_today",
    "pq_bi_monolingualism",
    "pq_native_language_1",
    "pq_native_language_2",
    "pq_native_language_3",
    "pq_use_language",
    "pq_dominant_language",
    "pq_additional_read_language_1",
    "pq_additional_read_language_2",
    "pq_additional_read_language_3",
    "pq_additional_read_language_4",
    "pq_language_reading_times",
)

_PSYCHOMETRIC_SCORE_FIELDS = (
    (
        "LWMC",
        "LWMC_Done",
        "LWMC done",
        "Whether the LWMC test was completed.",
        "boolean",
        "",
    ),
    (
        "LWMC",
        "LWMC_Total_score_mean",
        "LWMC total score mean",
        "Mean of the four LWMC subtask scores.",
        "number",
        "",
    ),
    (
        "RAN",
        "RAN_Done",
        "RAN done",
        "Whether the RAN test was completed.",
        "boolean",
        "",
    ),
    (
        "RAN",
        "RAN_experimental_rt_sec",
        "RAN experimental reaction time",
        "Mean experimental RAN reaction time.",
        "number",
        "s",
    ),
    (
        "Stroop",
        "Stroop_Done",
        "Stroop done",
        "Whether the Stroop test was completed.",
        "boolean",
        "",
    ),
    (
        "Stroop",
        "StroopRTEffect_sec",
        "Stroop reaction-time effect",
        "Incongruent minus congruent Stroop reaction time.",
        "number",
        "s",
    ),
    (
        "Flanker",
        "Flanker_Done",
        "Flanker done",
        "Whether the Flanker test was completed.",
        "boolean",
        "",
    ),
    (
        "Flanker",
        "FlankerRTEffect_sec",
        "Flanker reaction-time effect",
        "Incongruent minus congruent Flanker reaction time.",
        "number",
        "s",
    ),
    (
        "WikiVocab",
        "WikiVocab_Done",
        "WikiVocab done",
        "Whether the WikiVocab test was completed.",
        "boolean",
        "",
    ),
    (
        "WikiVocab",
        "WikiVocab_accuracy",
        "WikiVocab accuracy",
        "WikiVocab accuracy as a proportion from 0 to 1.",
        "number",
        "",
    ),
    (
        "PLAB",
        "PLAB_Done",
        "PLAB done",
        "Whether the PLAB test was completed.",
        "boolean",
        "",
    ),
    (
        "PLAB",
        "PLAB_accuracy",
        "PLAB accuracy",
        "PLAB accuracy as a proportion from 0 to 1.",
        "number",
        "",
    ),
)


def _label(name: str) -> str:
    text = name.removeprefix("pq_").replace("_", " ")
    return text[:1].upper() + text[1:]


def _pq_field(name: str) -> CodebookField:
    description = f"Normalized participant questionnaire field {name}."
    data_type = "number" if name in _PQ_NUMBER_FIELDS else "string"
    if name == "pq_bi_monolingualism":
        description = (
            "Language background derived from the distinct native languages: "
            "monolingual, bilingual or multilingual."
        )
    elif name == "pq_language_reading_times":
        description = (
            "Per-language reading-time answers keyed by language slot and question."
        )
        data_type = "object"
    return CodebookField(
        variable_id=f"participant.{name}",
        view_level="participant",
        variable_name=name,
        feature_label=_label(name),
        description=description,
        data_type=data_type,
        source_section="questionnaire",
        pipeline_field=name,
        yaml_path=f"participants[].{name}",
        semantic_category="participant",
        aggregation_behavior="static",
    )


def _psychometric_field(
    test: str,
    variable_name: str,
    feature_label: str,
    description: str,
    data_type: str,
    unit: str,
) -> CodebookField:
    return CodebookField(
        variable_id=f"participant.psychometric_tests.{test}.{variable_name}",
        view_level="participant",
        variable_name=variable_name,
        feature_label=feature_label,
        description=description,
        data_type=data_type,
        unit=unit,
        source_section="psychometric_tests",
        pipeline_field=variable_name,
        yaml_path=f"participants[].psychometric_tests.{test}.{variable_name}",
        semantic_category="participant",
        aggregation_behavior="static",
        notes="Curated subset. The full result table remains in psychometric_results_<dcn>.csv.",
    )


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
    CodebookField(
        variable_id="participant.source_pids",
        view_level="participant",
        variable_name="source_pids",
        feature_label="Source PIDs",
        description="All source participant IDs combined into the participant group.",
        data_type="list[string]",
        source_section="administrative",
        pipeline_field="pids",
        yaml_path="participants[].source_pids",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="A participant group can combine more than one source PID.",
    ),
    CodebookField(
        variable_id="participant.session_ids",
        view_level="participant",
        variable_name="session_ids",
        feature_label="Eye-tracking session IDs",
        description="All eye-tracking session IDs attributed to the participant group.",
        data_type="list[string]",
        source_section="administrative",
        pipeline_field="et_session_ids",
        yaml_path="participants[].session_ids",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="A participant group can contain multiple eye-tracking sessions.",
    ),
    CodebookField(
        variable_id="participant.psychometric_session_ids",
        view_level="participant",
        variable_name="psychometric_session_ids",
        feature_label="Psychometric session IDs",
        description="All psychometric-test session IDs attributed to the participant group.",
        data_type="list[string]",
        source_section="administrative",
        pipeline_field="pt_session_ids",
        yaml_path="participants[].psychometric_session_ids",
        semantic_category="administrative",
        aggregation_behavior="not_applicable",
        notes="A participant group can contain multiple psychometric-test sessions.",
    ),
    *(_pq_field(name) for name in _PQ_FIELDS),
    *(_psychometric_field(*definition) for definition in _PSYCHOMETRIC_SCORE_FIELDS),
    CodebookField(
        variable_id="participant.documentation.participant_csv",
        view_level="participant",
        variable_name="participant_csv",
        feature_label="Participant CSV",
        description="Relative path to the full participant download table.",
        data_type="string",
        source_section="documentation",
        pipeline_field="participants.csv",
        yaml_path="participants[].documentation.participant_csv",
        semantic_category="provenance",
        aggregation_behavior="not_applicable",
        notes="The full participant table remains participants.csv.",
    ),
    CodebookField(
        variable_id="participant.documentation.note",
        view_level="participant",
        variable_name="note",
        feature_label="Participant documentation note",
        description="Note that points users to the full participant download table.",
        data_type="string",
        source_section="documentation",
        pipeline_field="participants.csv",
        yaml_path="participants[].documentation.note",
        semantic_category="provenance",
        aggregation_behavior="not_applicable",
        notes="The YAML view is curated and does not duplicate every CSV column.",
    ),
)
