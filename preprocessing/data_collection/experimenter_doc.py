from pathlib import Path

import polars as pl


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

    pt_columns = [
        "date",
        "session_id",
        "participant_id",
        "session_start",
        "test",
        "comments",
        "session_end",
    ]

    et_sheet_name = "Documentation Experiment"
    pt_sheet_name = "Documentation Psychometr. Tests"

    def __init__(
        self,
        et_frame: pl.DataFrame | None,
        et_col_desc: tuple[str] | None,
        pt_frame: pl.DataFrame | None,
        pt_col_desc: tuple | None,
    ):
        self.et_frame = et_frame
        self.et_col_desc = et_col_desc
        self.pt_frame = pt_frame
        self.pt_col_desc = pt_col_desc

    def __repr__(self):
        return str({"et_frame": self.et_frame, "pt_frame": self.pt_frame})

    @classmethod
    def create_from_excel(cls, xl_path: Path) -> "ExperimenterDoc":
        doc_frame = pl.read_excel(xl_path, sheet_id=0, has_header=False)

        if cls.et_sheet_name in doc_frame:
            et_frame = doc_frame[cls.et_sheet_name]
            et_frame.columns = cls.et_columns
            et_header_idx = et_frame["date"].to_list().index("Date (dd-mm-yyyy)")
            et_col_desc = et_frame.row(et_header_idx)
            et_frame = et_frame.slice(et_header_idx + 1)
        else:
            print(
                f"Documentation sheet does not contain a sheet named {cls.et_sheet_name}. Skipping"
            )
            et_frame = None
            et_col_desc = None

        if cls.pt_sheet_name in doc_frame:
            pt_frame = doc_frame[cls.pt_sheet_name]
            pt_frame.columns = cls.pt_columns
            pt_header_idx = pt_frame["date"].to_list().index("Date (dd-mm-yyyy)")
            pt_col_desc = pt_frame.row(pt_header_idx)
            pt_frame = pt_frame.slice(pt_header_idx + 1)
        else:
            print(
                f"Documentation sheet does not contain a sheet named {cls.pt_sheet_name}. Skipping"
            )
            pt_frame = None
            pt_col_desc = None

        return cls(et_frame, et_col_desc, pt_frame, pt_col_desc)

    def get_pids(self, sheet: str) -> tuple[list[int], list[str]]:
        """Try to convert all p_ids on sheet ("et" or "pt") to integers.
        Returns list of recovered integer participant ids and a list of unconvertable participant ids.
        """

        if sheet not in ("et", "pt"):
            raise ValueError(f"sheet must be 'et' or 'pt' not {sheet}")

        if sheet == "et":
            pid_col = self.et_frame["participant_id"]
        else:
            pid_col = self.pt_frame["participant_id"]

        pid_int = list(pid_col.cast(pl.Int32, strict=False))

        invalid_ids = []

        for str_id, int_id in zip(pid_col, pid_int):
            if not int_id:
                invalid_ids.append(str_id)
                continue

        valid_ids = [id for id in pid_int if id]

        return (invalid_ids, valid_ids)
