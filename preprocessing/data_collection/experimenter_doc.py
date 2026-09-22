import polars as pl
from pathlib import Path


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
    "comments"
    ]

    pt_columns = [
    "date",
    "session_id",
    "participant_id",
    "session_start",
    "test",
    "comments",
    "session_end"
    ]

    et_sheet_name = "Documentation Experiment"
    pt_sheet_name = "Documentation Psychometr. Tests"

    et_header_idx = 2
    pt_header_idx = 0

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
        return str({
            "et_frame": self.et_frame,
            "pt_frame": self.pt_frame
        })

    @classmethod
    def create_from_excel(
        cls,
        xl_path: Path
    ) -> "ExperimenterDoc":
        doc_frame = pl.read_excel(xl_path, sheet_id = 0, has_header=False)

        if cls.et_sheet_name in doc_frame.keys():
            et_frame = doc_frame[cls.et_sheet_name]
            et_frame.columns = cls.et_columns
            et_col_desc = et_frame.row(cls.et_header_idx)
            et_frame = et_frame.slice(cls.et_header_idx+1)
        else:
            print(f"Documentation sheet does not contain a sheet named {cls.et_sheet_name}. Skipping")
            et_frame = None
            et_col_desc = None

        if cls.pt_sheet_name in doc_frame.keys():
            pt_frame = doc_frame[cls.pt_sheet_name]
            pt_frame.columns = cls.pt_columns
            pt_col_desc = pt_frame.row(cls.pt_header_idx)
            pt_frame = pt_frame.slice(cls.pt_header_idx+1)
        else:
            print(f"Documentation sheet does not contain a sheet named {cls.pt_sheet_name}. Skipping")
            pt_frame = None
            pt_col_desc = None

        return cls(et_frame, et_col_desc, pt_frame, pt_col_desc)
