import polars as pl

from preprocessing.utils.time_columns import time_column_to_ms, time_columns_to_ms


def test_time_columns_to_ms_converts_duration():
    frame = pl.DataFrame(
        {
            "time": pl.Series([1_000_000, 2_500_000], dtype=pl.Int64).cast(
                pl.Duration("us")
            )
        }
    )

    converted = time_columns_to_ms(frame, ["time"])

    assert converted.schema["time"] == pl.Int64
    assert converted["time"].to_list() == [1000, 2500]


def test_time_columns_to_ms_leaves_numeric_columns_unchanged():
    frame = pl.DataFrame({"time": [1000, 2500]})

    converted = time_columns_to_ms(frame, ["time"])

    assert converted.schema["time"] == pl.Int64
    assert converted["time"].to_list() == [1000, 2500]


def test_time_columns_to_ms_ignores_missing_columns():
    frame = pl.DataFrame({"time": [1000]})

    converted = time_columns_to_ms(frame, ["missing"])

    assert converted.equals(frame)


def test_time_columns_to_ms_returns_none():
    assert time_columns_to_ms(None, ["time"]) is None


def test_time_column_to_ms_uses_frame_dtype():
    duration_frame = pl.DataFrame(
        {"time": pl.Series([1000], dtype=pl.Int64).cast(pl.Duration("ms"))}
    )
    numeric_frame = pl.DataFrame({"time": [1000]})

    duration_result = duration_frame.select(time_column_to_ms(duration_frame))
    numeric_result = numeric_frame.select(time_column_to_ms(numeric_frame))

    assert duration_result["time"].to_list() == [1000]
    assert numeric_result["time"].to_list() == [1000]
