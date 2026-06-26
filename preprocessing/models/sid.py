from dataclasses import dataclass, field
from pathlib import Path
import re

__all__ = ["Sid"]


@dataclass
class Sid:
    pid: str = field(init=False)
    lang: str = field(init=False)
    country: str = field(init=False)
    lab: str = field(init=False)
    session: str = field(init=False)
    session_id: int = field(default=None, init=False)
    postfix: str = field(init=False)

    def __init__(
        self,
        sid: str | None = None,
        *,
        pid: str | None = None,
        lang: str | None = None,
        country: str | None = None,
        lab: str | None = None,
        session: str | None = None,
        postfix: str = "",
    ):
        if sid is not None and any(
            v is not None for v in [pid, lang, country, lab, session]
        ):
            raise ValueError(
                "Pass either 'sid' string or individual components, not both."
            )

        if sid is not None:
            if not isinstance(sid, str):
                raise TypeError(f"SID must be a string, got {type(sid).__name__}")
            parts = sid.split("_")
            if len(parts) < 5:
                raise ValueError(
                    f"Invalid SID format: '{sid}'. Expected at least 5 parts separated by '_'."
                )

            self.pid = parts[0]
            self.lang = parts[1]
            self.country = parts[2]
            self.lab = parts[3]
            self.session = parts[4]
            self.session_id = int(self.session[-1])
            self.postfix = "_".join(parts[5:]) if len(parts) > 5 else ""
        else:
            if any(v is None for v in [pid, lang, country, lab, session]):
                raise ValueError(
                    "All components (pid, lang, country, lab, session) must be provided if 'sid' is not."
                )

            self.pid = pid
            self.lang = lang
            self.country = country
            self.lab = lab
            self.session = session
            self.postfix = postfix

        self._validate()

    def _validate(self):
        if not re.match(r"^\d{3}$", self.pid):
            raise ValueError(f"Invalid PID: '{self.pid}'. Must be 3 digits.")
        if not re.match(r"^[A-Za-z]{2}$", self.lang):
            raise ValueError(
                f"Invalid language code: '{self.lang}'. Must be 2 letters."
            )
        if not re.match(r"^[A-Za-z]{2}$", self.country):
            raise ValueError(
                f"Invalid country code: '{self.country}'. Must be 2 letters."
            )
        if not self.lab:
            raise ValueError("Lab identifier cannot be empty.")
        if not self.session:
            raise ValueError("Session identifier cannot be empty.")
        if not re.match(r"^(S|PT|ET)\d+$", self.session):
            raise ValueError(
                f"Invalid session identifier: '{self.session}'. Must start with S, PT, or ET followed by digits."
            )

    @property
    def notes(self) -> str:
        parts = self.postfix.split("_")
        if (
            len(parts) >= 4
            and parts[0:3] == ["start", "after", "trial"]
            and parts[3].isdigit()
        ):
            trial = parts[3]
            return f"Session has been restarted after trial {trial}."
        elif len(parts) >= 2 and parts[0:2] == ["full", "restart"]:
            return "Session has been fully restarted."
        return ""

    @property
    def base_id(self) -> str:
        """Returns the SID without the session part."""
        base = f"{self.pid}_{self.lang}_{self.country}_{self.lab}"
        # the postfix does not have to be added really. But need to test it.
        # if self.postfix:
        #     return f"{base}_{self.postfix}"
        return base

    @property
    def id_no_postfix(self) -> str:
        """Returns the SID string without the restart postfix."""
        return f"{self.pid}_{self.lang}_{self.country}_{self.lab}_{self.session}"

    @property
    def raw_data_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.RAW_DATA_FOLDER / str(self)

    @property
    def fixations_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.FIXATIONS_FOLDER / str(self)

    @property
    def saccades_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.SACCADES_FOLDER / str(self)

    @property
    def scanpaths_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.SCANPATHS_FOLDER / str(self)

    @property
    def reading_measures_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.READING_MEASURES_FOLDER / str(self)

    @property
    def metadata_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.METADATA_FOLDER / str(self)

    @property
    def answers_dir(self) -> Path:
        from ..config import settings as _settings

        return _settings.OUTPUT_DIR / _settings.ANSWERS_FOLDER / str(self)

    @staticmethod
    def get_session_save_name(session_idf: str, include_postfix: bool = False) -> str:
        """Get a consistent session name for file names, optionally including restart postfixes."""
        try:
            sid = Sid(session_idf)
            return str(sid) if include_postfix else sid.id_no_postfix
        except (ValueError, TypeError):
            # Fallback for non-compliant identifiers
            return "_".join(session_idf.split("_")[:5])

    def __str__(self) -> str:
        base = self.id_no_postfix
        if self.postfix:
            return f"{base}_{self.postfix}"
        return base

    @staticmethod
    def is_valid_pid(pid: str) -> bool:
        """Checks if a participant identifier (PID) is valid (exactly 3 digits)."""
        return isinstance(pid, str) and bool(re.match(r"^\d{3}$", pid))

    @staticmethod
    def is_valid_sid(sid: str) -> bool:
        """Checks if a string is a valid SID-compliant identifier."""
        if not isinstance(sid, str):
            return False
        try:
            Sid(sid)
            return True
        except (ValueError, TypeError):
            return False

    def equals_soft(self, other: "Sid") -> bool:
        """
        Checks if two Sids are equivalent, allowing S/PT/ET prefix variation in the session part.
        Example: 001_EN_UK_1_S1 matches 001_EN_UK_1_PT1.
        Comparison is case-insensitive for language and country codes.
        """
        if not isinstance(other, Sid):
            return False

        # Check all parts except session and postfix
        if (
            self.pid != other.pid
            or self.lang.upper() != other.lang.upper()
            or self.country.upper() != other.country.upper()
            or self.lab != other.lab
        ):
            return False

        # Check session equivalence
        def normalize_session(s: str) -> str:
            # Matches S, PT, or ET followed by digits
            match = re.match(r"^(S|PT|ET)(\d+)$", s)
            if match:
                return f"NORM{match.group(2)}"
            return s

        return normalize_session(self.session) == normalize_session(other.session)
