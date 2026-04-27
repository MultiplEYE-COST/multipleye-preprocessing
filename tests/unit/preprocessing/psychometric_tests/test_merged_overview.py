import pytest
import pandas as pd
from pathlib import Path
from preprocessing.psychometric_tests.preprocess_psychometric_tests import create_merged_psychometric_overview

def test_create_merged_psychometric_overview_disjoint(tmp_path):
    # Create a dummy overview CSV
    data = [
        {
            "session_id": "001_HR_hr_1_PT1",
            "participant_id": "001",
            "LWMC_Done": 1,
            "RAN_Done": 0,
            "LWMC_Total_score_mean": 0.63,
            "notes": "note1"
        },
        {
            "session_id": "001_HR_hr_1_PT2",
            "participant_id": "001",
            "LWMC_Done": 0,
            "RAN_Done": 1,
            "RAN_experimental_rt_sec": 16.8,
            "notes": "note2"
        },
        {
            "session_id": "002_HR_hr_1_PT1",
            "participant_id": "002",
            "LWMC_Done": 1,
            "RAN_Done": 0,
            "LWMC_Total_score_mean": 0.81,
            "notes": ""
        }
    ]
    df = pd.DataFrame(data)
    overview_path = tmp_path / "psychometric_overview.csv"
    df.to_csv(overview_path, index=False)

    merged_path = create_merged_psychometric_overview(overview_path)

    assert merged_path.exists()
    assert merged_path.name == "psychometric_overview_merged.csv"

    merged_df = pd.read_csv(merged_path)
    
    # 001 should be merged
    p001 = merged_df[merged_df["participant_id"] == 1] # pandas might read as int
    if len(p001) == 0:
         p001 = merged_df[merged_df["participant_id"] == "001"]
    
    assert len(p001) == 1
    row001 = p001.iloc[0]
    assert row001["session_id"] == "001_HR_hr_1"
    assert row001["original_sessions"] == "001_HR_hr_1_PT1, 001_HR_hr_1_PT2"
    assert row001["LWMC_Done"] == 1
    assert row001["RAN_Done"] == 1
    assert row001["LWMC_Total_score_mean"] == 0.63
    assert row001["RAN_experimental_rt_sec"] == 16.8
    assert "note1" in row001["notes"]
    assert "note2" in row001["notes"]

    # 002 should stay as is but with renamed session_id base
    p002 = merged_df[merged_df["participant_id"] == 2]
    if len(p002) == 0:
        p002 = merged_df[merged_df["participant_id"] == "002"]
    assert len(p002) == 1
    assert p002.iloc[0]["session_id"] == "002_HR_hr_1"

def test_create_merged_psychometric_overview_overlap(tmp_path, caplog):
    import logging
    # Create a dummy overview CSV with overlapping tests
    data = [
        {
            "session_id": "001_HR_hr_1_PT1",
            "participant_id": "001",
            "LWMC_Done": 1,
            "LWMC_Total_score_mean": 0.63,
        },
        {
            "session_id": "001_HR_hr_1_PT2",
            "participant_id": "001",
            "LWMC_Done": 1,
            "LWMC_Total_score_mean": 0.88,
        }
    ]
    df = pd.DataFrame(data)
    overview_path = tmp_path / "psychometric_overview_overlap.csv"
    df.to_csv(overview_path, index=False)

    with caplog.at_level(logging.WARNING):
        merged_path = create_merged_psychometric_overview(overview_path)
    
    assert "overlapping results for LWMC_Done" in caplog.text
    
    merged_df = pd.read_csv(merged_path)
    # Should NOT be merged
    p001 = merged_df[merged_df["participant_id"] == 1]
    if len(p001) == 0:
        p001 = merged_df[merged_df["participant_id"] == "001"]
    assert len(p001) == 2

def test_create_merged_psychometric_overview_independent_merging(tmp_path):
    # Test that one participant's overlap does not prevent another from merging
    data = [
        # Participant 001: Should merge
        {"session_id": "001_HR_hr_1_PT1", "participant_id": "001", "LWMC_Done": 1, "RAN_Done": 0, "notes": "n1"},
        {"session_id": "001_HR_hr_1_PT2", "participant_id": "001", "LWMC_Done": 0, "RAN_Done": 1, "notes": "n2"},
        # Participant 002: Overlap, should NOT merge
        {"session_id": "002_HR_hr_1_PT1", "participant_id": "002", "LWMC_Done": 1, "RAN_Done": 0, "notes": "n3"},
        {"session_id": "002_HR_hr_1_PT2", "participant_id": "002", "LWMC_Done": 1, "RAN_Done": 1, "notes": "n4"},
    ]
    df = pd.DataFrame(data)
    overview_path = tmp_path / "psychometric_overview_independent.csv"
    df.to_csv(overview_path, index=False)

    merged_path = create_merged_psychometric_overview(overview_path)
    merged_df = pd.read_csv(merged_path)

    # 001 should be merged into 1 row
    p001 = merged_df[merged_df["participant_id"].astype(str).str.contains("1")]
    assert len(p001) == 1
    
    # 002 should NOT be merged, staying as 2 rows
    p002 = merged_df[merged_df["participant_id"].astype(str).str.contains("2")]
    assert len(p002) == 2
