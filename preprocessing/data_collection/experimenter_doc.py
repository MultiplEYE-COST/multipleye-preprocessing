from __future__ import annotations

import re
from pathlib import Path

import polars as pl

_WHITESPACE = re.compile(r"\s+")


def _normalize_header(value: object) -> str:
    """Return a case- and whitespace-insensitive header string."""
    return _WHITESPACE.sub(" ", str(value)).strip().lower()


class ExperimenterDoc:
    et_columns = [
        "date",
        "session_id",
        "participant_id",
        "start_time",
        "end_time",
        "max_sampling_rate",
        "sampling_rate",
        "dominant_eye_test",
        "dominant_eye",
        "tracked_eye",
        "distance_monocular",
        "distance_binocular",
        "eyetracker",
        "camera_system",
        "correct_validation_procedure",
        "actual_validation_performance",
        "calibration_error",
        "re-calibration_within_trials",
        "re-calibration_between_trials",
        "calibration_issues",
        "avg_calibration_error",
        "validation_issues",
        "tracked_eye_changed",
        "mandatory_breaks",
        "mandatory_breaks_reason",
        "break_length",
        "optional_breaks",
        "interruptions",
        "irritations",
        "abortion",
        "setup_deviation",
        "technical_issues",
        "pq_issues",
        "participant_incidents",
        "others_present",
        "lighting_deviation",
        "file_issues",
        "comments",
    ]

    et_header_prefixes = {
        "date": "date (dd-mm-yyyy)",
        "session_id": "session id",
        "participant_id": "participant id",
        "start_time": "time of the start of the experiment",
        "end_time": "time of the end of the experiment",
        "max_sampling_rate": "maximal sampling rate",
        "sampling_rate": "actual sampling rate",
        "dominant_eye_test": "did you test for the dominant eye",
        "dominant_eye": "if the dominant eye test was successful",
        "tracked_eye": "tracked eye",
        "distance_monocular": "provide information on distances for monocular",
        "distance_binocular": "provide information on distances for binocular",
        "eyetracker": "eye tracker model",
        "camera_system": "eye tracker camera system",
        "correct_validation_procedure": "calibration & validation performance",
        "actual_validation_performance": "other amount of validation performance",
        "calibration_error": "calibration error data",
        "re-calibration_within_trials": "re-calibration was performed within a trial",
        "re-calibration_between_trials": "re-calibration was performed between two trials",
        "calibration_issues": "were there any specific difficulties with calibration",
        "avg_calibration_error": "what is the average calibration error",
        "validation_issues": "any validation issues",
        "tracked_eye_changed": "monocular tracking: change of tracked eye",
        "mandatory_breaks": "have you used the mandatory breaks",
        "mandatory_breaks_reason": "if you haven't used the mandatory break",
        "break_length": "if you have used the mandatory break",
        "optional_breaks": "did you use any optional breaks",
        "interruptions": "were there any other interruptions",
        "irritations": "are there any sources of irritation",
        "abortion": "abortion of session",
        "setup_deviation": "lab setup deviation",
        "technical_issues": "were there any technical issues",
        "pq_issues": "were there any issues to the participant questionnaire",
        "participant_incidents": "were there any incidents relating to the participant",
        "others_present": "presence of others",
        "lighting_deviation": "lighting condition deviation",
        "file_issues": "were there any deviations / errors / mistakes",
        "comments": "additional comments",
    }

    pt_columns = [
        "date",
        "session_id",
        "participant_id",
        "session_start",
        "test",
        "comments",
        "session_end",
    ]

    pt_required_columns = [
        "date",
        "session_id",
        "participant_id",
        "session_start",
        "test",
        "comments",
    ]

    pt_header_prefixes = {
        "date": "date (dd-mm-yyyy)",
        "session_id": "session id",
        "participant_id": "participant id",
        "session_start": "time of the start of the session",
        "test": "name of psychometric test",
        "comments": "comments/notes",
        "session_end": "time of the end of the session",
    }

    et_sheet_name = "Documentation Experiment"
    pt_sheet_name = "Documentation Psychometr. Tests"

    def __init__(
        self,
        et_frame: pl.DataFrame | None,
        et_col_desc: tuple[object, ...] | None,
        pt_frame: pl.DataFrame | None,
        pt_col_desc: tuple[object, ...] | None,
    ):
        self.et_frame = et_frame
        self.et_col_desc = et_col_desc
        self.pt_frame = pt_frame
        self.pt_col_desc = pt_col_desc

    def __repr__(self):
        return str({"et_frame": self.et_frame, "pt_frame": self.pt_frame})

    @classmethod
    def create_from_excel(cls, xl_path: Path) -> ExperimenterDoc:
        """Read the experimenter documentation workbook.

        Columns are matched by their header text and may be reordered. Columns
        added by a lab are kept under their original header. When a sheet layout
        does not match the expected headers, the expected column order is used
        as a fallback.

        Raises
        ------
        ValueError
            If a required sheet, the header row, or a required column cannot be
            found.
        """
        sheets = pl.read_excel(
            xl_path,
            sheet_id=0,
            has_header=False,
            drop_empty_rows=False,
            drop_empty_cols=False,
        )

        et_frame, et_col_desc = cls._parse_sheet(
            sheets,
            cls.et_sheet_name,
            cls.et_columns,
            cls.et_header_prefixes,
            cls.et_columns,
        )
        pt_frame, pt_col_desc = cls._parse_sheet(
            sheets,
            cls.pt_sheet_name,
            cls.pt_columns,
            cls.pt_header_prefixes,
            cls.pt_required_columns,
        )

        return cls(et_frame, et_col_desc, pt_frame, pt_col_desc)

    @classmethod
    def _parse_sheet(
        cls,
        sheets: dict[str, pl.DataFrame],
        sheet_name: str,
        columns: list[str],
        prefixes: dict[str, str],
        required: list[str],
    ) -> tuple[pl.DataFrame, tuple[object, ...]]:
        if sheet_name not in sheets:
            raise ValueError(
                f"The experimenter documentation workbook has no sheet named "
                f"{sheet_name!r}."
            )

        frame = sheets[sheet_name]
        header_idx = cls._find_header_row(frame)
        header_row = frame.row(header_idx)
        mapping = cls._match_columns(header_row, prefixes)
        missing = [name for name in required if name not in mapping]

        if not missing:
            return cls._build_frame(frame, header_idx, mapping, columns), header_row

        # Fall back to the expected column order for a known layout.
        for layout in cls._fallback_layouts(columns, required):
            if frame.width == len(layout):
                body = frame.slice(header_idx + 1)
                body.columns = layout
                return body, header_row

        raise ValueError(
            f"Could not map all required columns in sheet {sheet_name!r}. "
            f"Missing: {', '.join(missing)}. "
            f"Found {frame.width} columns; expected one of the known layouts "
            "or matching headers."
        )

    @classmethod
    def _fallback_layouts(
        cls, columns: list[str], required: list[str]
    ) -> list[list[str]]:
        layouts = [columns]
        if required != columns:
            layouts.append(required)
        return layouts

    @classmethod
    def _find_header_row(cls, frame: pl.DataFrame) -> int:
        """Return the index of the row containing the documentation headers."""
        for idx in range(frame.height):
            normalized = {_normalize_header(value) for value in frame.row(idx)}
            if (
                any(value.startswith("date (dd-mm-yyyy)") for value in normalized)
                and "session id" in normalized
                and "participant id" in normalized
            ):
                return idx
        raise ValueError(
            "Could not locate the header row in the experimenter documentation "
            "sheet. Expected a row with 'Date (dd-mm-yyyy)', 'Session ID' and "
            "'Participant ID'."
        )

    @classmethod
    def _match_columns(
        cls, header_row: tuple[object, ...], prefixes: dict[str, str]
    ) -> dict[str, int]:
        """Map canonical column names to positions using header prefixes."""
        normalized = [_normalize_header(value) for value in header_row]
        mapping: dict[str, int] = {}
        for name, prefix in prefixes.items():
            matches = [
                idx for idx, value in enumerate(normalized) if value.startswith(prefix)
            ]
            if len(matches) == 1:
                mapping[name] = matches[0]
        return mapping

    @classmethod
    def _build_frame(
        cls,
        frame: pl.DataFrame,
        header_idx: int,
        mapping: dict[str, int],
        columns: list[str],
    ) -> pl.DataFrame:
        """Select canonical columns and keep unmatched lab columns as extras."""
        header = frame.row(header_idx)
        body = frame.slice(header_idx + 1)
        series: dict[str, pl.Series] = {}
        used: set[int] = set()

        for name in columns:
            if name in mapping:
                series[name] = body[:, mapping[name]]
                used.add(mapping[name])

        for idx in range(body.width):
            if idx in used:
                continue
            raw = str(header[idx]).strip() if idx < len(header) else ""
            extra = raw or f"extra_{idx}"
            if extra in series:
                extra = f"{extra}_{idx}"
            series[extra] = body[:, idx]

        return pl.DataFrame(series)

    def get_pids(self, sheet: str) -> tuple[list[int], list[str]]:
        """Return ``(valid_ids, invalid_ids)`` for the ET or PT sheet."""
        if sheet == "et":
            frame = self.et_frame
        elif sheet == "pt":
            frame = self.pt_frame
        else:
            raise ValueError(f"sheet must be 'et' or 'pt' not {sheet!r}")

        if frame is None:
            raise ValueError(f"No data available for the {sheet!r} sheet.")
        if "participant_id" not in frame.columns:
            raise ValueError(
                f"The {sheet!r} sheet has no 'participant_id' column after parsing."
            )

        valid_ids: list[int] = []
        invalid_ids: list[str] = []
        for value in frame["participant_id"].to_list():
            text = "" if value is None else str(value).strip()
            if not text:
                continue
            try:
                valid_ids.append(int(text))
            except (TypeError, ValueError):
                try:
                    number = float(text)
                except (TypeError, ValueError):
                    invalid_ids.append(text)
                    continue
                if not number.is_integer():
                    invalid_ids.append(text)
                    continue
                valid_ids.append(int(number))

        return valid_ids, invalid_ids
