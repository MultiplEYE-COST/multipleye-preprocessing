from dataclasses import dataclass, field
import re

__all__ = ["Dcn"]


@dataclass
class Dcn:
    prefix: str = field(init=False)
    lang: str = field(init=False)
    country: str = field(init=False)
    city: str = field(init=False)
    lab: str = field(init=False)
    year: str = field(init=False)

    def __init__(
        self,
        name: str | None = None,
        *,
        lang: str | None = None,
        country: str | None = None,
        city: str | None = None,
        lab: str | None = None,
        year: str | None = None,
    ):
        if name is not None and any(
            v is not None for v in [lang, country, city, lab, year]
        ):
            raise ValueError(
                "Pass either 'name' string or individual components, not both."
            )

        if name is not None:
            if not isinstance(name, str):
                raise TypeError(f"Name must be a string, got {type(name).__name__}")
            parts = name.split("_")
            if len(parts) != 6:
                raise ValueError(
                    f"Invalid data collection name format: '{name}'. Expected 6 parts separated by '_'."
                )

            self.prefix = parts[0]
            self.lang = parts[1]
            self.country = parts[2]
            self.city = parts[3]
            self.lab = parts[4]
            self.year = parts[5]
        else:
            if any(v is None for v in [lang, country, city, lab, year]):
                raise ValueError(
                    "All components (lang, country, city, lab, year) must be provided if 'name' is not."
                )

            self.prefix = "MultiplEYE"
            self.lang = lang
            self.country = country
            self.city = city
            self.lab = lab
            self.year = year

        self._validate()

    def _validate(self):
        if self.prefix != "MultiplEYE":
            raise ValueError(f"Invalid prefix: '{self.prefix}'. Must be 'MultiplEYE'.")
        if not re.match(r"^[A-Z]{2}$", self.lang):
            raise ValueError(
                f"Invalid language code: '{self.lang}'. Must be 2 uppercase letters."
            )
        if not re.match(r"^[A-Z]{2}$", self.country):
            raise ValueError(
                f"Invalid country code: '{self.country}'. Must be 2 uppercase letters."
            )
        if not re.match(r"^[A-Za-z0-9]+$", self.city):
            raise ValueError(f"Invalid city: '{self.city}'. Must be alphanumeric.")
        if not re.match(r"^[A-Za-z0-9]+$", self.lab):
            raise ValueError(f"Invalid lab: '{self.lab}'. Must be alphanumeric.")
        if not re.match(r"^\d{4}$", self.year):
            raise ValueError(f"Invalid year: '{self.year}'. Must be 4 digits.")

    def __str__(self) -> str:
        return f"{self.prefix}_{self.lang}_{self.country}_{self.city}_{self.lab}_{self.year}"

    @staticmethod
    def is_valid(name: str) -> bool:
        """Checks if a string is a valid Dcn-compliant identifier."""
        if not isinstance(name, str):
            return False
        try:
            Dcn(name)
            return True
        except (ValueError, TypeError):
            return False
