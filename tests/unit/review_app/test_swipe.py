"""Tests for swipe service — per-plot judgment read/write."""

from pathlib import Path

import pytest
import yaml


def test_load_judgments_missing(monkeypatch):
    from review_app.services.swipe import load_judgments

    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", Path("/tmp/nonexistent"))
    assert load_judgments("test_dcn") == {}


def test_save_and_load_plot_judgment(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_judgments, save_plot_judgment

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    data = load_judgments("dcn1")
    assert data["sid1"]["plots"]["plot_a"] == "keep"
    assert data["sid1"]["comments"] == {}


def test_save_multiple_plots(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_judgments, save_plot_judgment

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    save_plot_judgment("dcn1", "sid1", "plot_b", "flag")

    data = load_judgments("dcn1")
    assert data["sid1"]["plots"] == {"plot_a": "keep", "plot_b": "flag"}


def test_remove_plot_judgment(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import (
        load_judgments,
        remove_plot_judgment,
        save_plot_judgment,
    )

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    save_plot_judgment("dcn1", "sid1", "plot_b", "flag")
    remove_plot_judgment("dcn1", "sid1", "plot_a")

    data = load_judgments("dcn1")
    assert "plot_a" not in data["sid1"]["plots"]
    assert data["sid1"]["plots"]["plot_b"] == "flag"


def test_remove_last_plot_removes_session(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import (
        load_judgments,
        remove_plot_judgment,
        save_plot_judgment,
    )

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    remove_plot_judgment("dcn1", "sid1", "plot_a")

    data = load_judgments("dcn1")
    assert "sid1" not in data


def test_save_plot_comment(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_judgments, save_plot_comment

    save_plot_comment("dcn1", "sid1", "plot_a", "Looks good")
    data = load_judgments("dcn1")
    assert data["sid1"]["comments"]["plot_a"] == "Looks good"
    assert data["sid1"]["plots"] == {}


def test_save_empty_comment_removes_it(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_judgments, save_plot_comment

    save_plot_comment("dcn1", "sid1", "plot_a", "Some note")
    save_plot_comment("dcn1", "sid1", "plot_a", "")

    data = load_judgments("dcn1")
    assert "plot_a" not in data["sid1"].get("comments", {})


def test_invalid_judgment_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    import pytest

    from review_app.services.swipe import save_plot_judgment

    with pytest.raises(ValueError, match="Invalid judgment"):
        save_plot_judgment("dcn1", "sid1", "plot_a", "bogus")


def test_yaml_format(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import save_plot_comment, save_plot_judgment

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    save_plot_judgment("dcn1", "sid1", "plot_b", "flag")
    save_plot_comment("dcn1", "sid1", "plot_a", "Nice")

    yaml_path = tmp_path / "dcn1" / "swipe_judgments.yaml"
    assert yaml_path.exists()

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    assert raw == {
        "sid1": {
            "plots": {"plot_a": "keep", "plot_b": "flag"},
            "comments": {"plot_a": "Nice"},
        }
    }


def test_load_session_judgment(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import (
        load_session_judgment,
        save_plot_judgment,
    )

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    save_plot_judgment("dcn1", "sid1", "plot_b", "keep")
    assert load_session_judgment("dcn1", "sid1") == "keep"


def test_load_session_judgment_mixed(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import (
        load_session_judgment,
        save_plot_judgment,
    )

    save_plot_judgment("dcn1", "sid1", "plot_a", "keep")
    save_plot_judgment("dcn1", "sid1", "plot_b", "flag")
    assert load_session_judgment("dcn1", "sid1") == "flag"


def test_load_session_judgment_none(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_session_judgment

    assert load_session_judgment("dcn1", "sid1") is None


def test_load_plot_judgments_dict(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import (
        load_plot_judgments_dict,
        save_plot_judgment,
    )

    save_plot_judgment("dcn1", "sid1", "plot_a", "flag")
    result = load_plot_judgments_dict("dcn1", "sid1")
    assert result == {"plot_a": "flag"}


def test_load_plot_comments_dict(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import load_plot_comments_dict, save_plot_comment

    save_plot_comment("dcn1", "sid1", "plot_a", "Comment text")
    result = load_plot_comments_dict("dcn1", "sid1")
    assert result == {"plot_a": "Comment text"}


def test_swipe_stats_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    from review_app.services.swipe import swipe_stats

    stats = swipe_stats("dcn1")
    assert stats["plots_judged"] == 0
    assert stats["total_plots"] == 0
    assert stats["progress_pct"] == 0


# ---------------------------------------------------------------------------
# swipe_stats edge cases
# ---------------------------------------------------------------------------


def _make_swipe_stats(sessions, plot_map, judgments_dict, monkeypatch):
    """Helper: monkeypatch swipe_stats dependencies and call it."""
    from review_app.services import swipe as swipe_mod

    def _fake_list_sessions(_dcn):
        return sessions

    def _fake_list_plot_data(_dcn, sid):
        return [
            {
                "name": p,
                "url": f"/files/{p}.png",
                "stimulus": p,
                "page": "",
                "activity": "",
            }
            for p in plot_map.get(sid, [])
        ]

    monkeypatch.setattr(swipe_mod, "list_sessions", _fake_list_sessions)
    monkeypatch.setattr(swipe_mod, "list_plot_data", _fake_list_plot_data)

    # Write judgments YAML so load_judgments can read it
    from review_app.config import REVIEW_DATA_DIR

    jpath = REVIEW_DATA_DIR / "test_dcn" / "swipe_judgments.yaml"
    jpath.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    with open(jpath, "w") as f:
        yaml.dump(judgments_dict, f)

    from review_app.services.swipe import swipe_stats

    return swipe_stats("test_dcn")


class FakeSession:
    def __init__(self, sid, n_flags=0, n_fail_flags=0, n_warn_flags=0):
        self.sid = sid
        self.pid = 0
        self.is_pilot = False
        self.n_flags = n_flags
        self.n_fail_flags = n_fail_flags
        self.n_warn_flags = n_warn_flags
        self.review_status = "unreviewed"
        self.reviewer = ""
        self.comment_preview = ""
        self.num_completed_trials = None
        self.needs_reprocessing = False


@pytest.mark.parametrize(
    "sessions,plot_map,judgments,expected",
    [
        pytest.param(
            [],
            {},
            {},
            {
                "plots_judged": 0,
                "total_plots": 0,
                "keep": 0,
                "flag": 0,
                "skip": 0,
                "sessions_complete": 0,
                "sessions_skipped": 0,
                "total_sessions": 0,
                "progress_pct": 0,
            },
            id="empty",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": ["p1", "p2"], "s2": ["p3", "p4"]},
            {
                "s1": {"plots": {"p1": "keep", "p2": "flag"}, "comments": {}},
                "s2": {"plots": {"p3": "skip", "p4": "keep"}, "comments": {}},
            },
            {
                "plots_judged": 4,
                "total_plots": 4,
                "keep": 2,
                "flag": 1,
                "skip": 1,
                "sessions_complete": 2,
                "sessions_skipped": 0,
                "total_sessions": 2,
                "progress_pct": 100.0,
            },
            id="all_complete_mixed",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": ["p1", "p2"], "s2": ["p3", "p4"]},
            {"s1": {"plots": {"p1": "keep"}, "comments": {}}},
            {
                "plots_judged": 1,
                "total_plots": 4,
                "keep": 1,
                "flag": 0,
                "skip": 0,
                "sessions_complete": 0,
                "sessions_skipped": 1,
                "total_sessions": 2,
                "progress_pct": 25.0,
            },
            id="one_partial_no_other",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": ["p1", "p2"], "s2": ["p3", "p4"]},
            {
                "s1": {"plots": {"p1": "keep", "p2": "flag"}, "comments": {}},
                "s2": {"plots": {"p3": "skip"}, "comments": {}},
            },
            {
                "plots_judged": 3,
                "total_plots": 4,
                "keep": 1,
                "flag": 1,
                "skip": 1,
                "sessions_complete": 1,
                "sessions_skipped": 1,
                "total_sessions": 2,
                "progress_pct": 75.0,
            },
            id="one_complete_one_skipped",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": ["p1", "p2"], "s2": ["p3", "p4"]},
            {},
            {
                "plots_judged": 0,
                "total_plots": 4,
                "keep": 0,
                "flag": 0,
                "skip": 0,
                "sessions_complete": 0,
                "sessions_skipped": 0,
                "total_sessions": 2,
                "progress_pct": 0.0,
            },
            id="none_judged",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": ["p1"], "s2": ["p2"]},
            {
                "s1": {"plots": {"p1": "keep"}, "comments": {}},
                "s2": {"plots": {"p2": "flag"}, "comments": {}},
            },
            {
                "plots_judged": 2,
                "total_plots": 2,
                "keep": 1,
                "flag": 1,
                "skip": 0,
                "sessions_complete": 2,
                "sessions_skipped": 0,
                "total_sessions": 2,
                "progress_pct": 100.0,
            },
            id="single_plot_sessions",
        ),
        pytest.param(
            [FakeSession("s1"), FakeSession("s2")],
            {"s1": [], "s2": ["p2"]},
            {"s2": {"plots": {"p2": "keep"}, "comments": {}}},
            {
                "plots_judged": 1,
                "total_plots": 1,
                "keep": 1,
                "flag": 0,
                "skip": 0,
                "sessions_complete": 1,
                "sessions_skipped": 0,
                "total_sessions": 2,
                "progress_pct": 100.0,
            },
            id="session_with_no_plots_excluded",
        ),
    ],
)
def test_swipe_stats_edge_cases(
    sessions, plot_map, judgments, expected, tmp_path, monkeypatch
):
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    stats = _make_swipe_stats(sessions, plot_map, judgments, monkeypatch)
    for key, val in expected.items():
        assert stats[key] == val, (
            f"Mismatch for {key}: expected {val}, got {stats[key]}"
        )


def test_parse_plot_name():
    from review_app.services.swipe import _parse_plot_name

    assert _parse_plot_name("main_sequence") == {
        "stimulus": "Main Sequence",
        "page": "",
        "activity": "",
    }
    assert _parse_plot_name("stim1_2") == {
        "stimulus": "stim1",
        "page": "page 2",
        "activity": "",
    }
    assert _parse_plot_name("stim1_q3") == {
        "stimulus": "stim1",
        "page": "question 3",
        "activity": "",
    }
    # 3-part name with page in middle: parser takes last part as activity
    result = _parse_plot_name("stim1_2_reading")
    assert result["stimulus"] == "stim1"
    assert result["activity"] == "reading"
    # page is empty because parser only checks parts[-1] for digit
    assert result["page"] == ""
