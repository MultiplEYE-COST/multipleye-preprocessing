import polars as pl
from preprocessing.io.load import load_reading_measures


def test_load_reading_measures_with_actual_filenames(tmp_path):
    # Setup: Create dummy reading measures files with the reported naming convention
    session = "017_DA_DK_1_ET1"
    reading_measures_dir = tmp_path / session / "reading_measures"
    reading_measures_dir.mkdir(parents=True)

    # Files as reported in the issue
    filenames = [
        f"{session}_PRACTICE_trial_1_Enc_WikiMoon_reading_measures.csv",
        f"{session}_trial_1_Lit_MagicMountain_reading_measures.csv",
        f"{session}_trial_5_PopSci_MultiplEYE_reading_measures.csv",
    ]

    for filename in filenames:
        df = pl.DataFrame({"measure": [1.0], "trial": ["dummy"], "stimulus": ["dummy"]})
        df.write_csv(reading_measures_dir / filename)

    # Test loading
    df_loaded = load_reading_measures(reading_measures_dir)

    assert len(df_loaded) == 3
    assert set(df_loaded["trial"].unique()) == {
        "PRACTICE_trial_1",
        "trial_1",
        "trial_5",
    }
    assert set(df_loaded["stimulus"].unique()) == {
        "Enc_WikiMoon",
        "Lit_MagicMountain",
        "PopSci_MultiplEYE",
    }
