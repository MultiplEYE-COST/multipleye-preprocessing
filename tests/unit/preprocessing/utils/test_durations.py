import polars as pl

from preprocessing.utils.durations import durations_to_ms


def test_durations_to_ms_converts_whole_milliseconds_to_int():
    frame = pl.DataFrame(
        {
            "time": pl.Series([1_000_000, 2_500_000], dtype=pl.Int64).cast(
                pl.Duration("us")
            )
        }
    )

    converted = durations_to_ms(frame)

    assert converted.schema["time"] == pl.Int64
    assert converted["time"].to_list() == [1000, 2500]


def test_durations_to_ms_keeps_fractional_milliseconds():
    frame = pl.DataFrame(
        {"time": pl.Series([1_500, 2_500], dtype=pl.Int64).cast(pl.Duration("us"))}
    )

    converted = durations_to_ms(frame)

    assert converted.schema["time"] == pl.Float64
    assert converted["time"].to_list() == [1.5, 2.5]


def test_durations_to_ms_converts_all_duration_columns():
    frame = pl.DataFrame(
        {
            "onset": pl.Series([1000], dtype=pl.Int64).cast(pl.Duration("us")),
            "duration": pl.Series([2000], dtype=pl.Int64).cast(pl.Duration("us")),
            "label": ["fixation"],
        }
    )

    converted = durations_to_ms(frame)

    assert converted["onset"].to_list() == [1]
    assert converted["duration"].to_list() == [2]
    assert converted["label"].to_list() == ["fixation"]


def test_durations_to_ms_leaves_numeric_columns_unchanged():
    frame = pl.DataFrame({"time": [1000, 2500]})

    converted = durations_to_ms(frame)

    assert converted.schema["time"] == pl.Int64
    assert converted["time"].to_list() == [1000, 2500]


def test_durations_to_ms_converts_empty_duration_column():
    frame = pl.DataFrame(schema={"time": pl.Duration("us")})

    converted = durations_to_ms(frame)

    assert converted.schema["time"] == pl.Int64
    assert converted.is_empty()


def test_durations_to_ms_returns_none():
    assert durations_to_ms(None) is None
