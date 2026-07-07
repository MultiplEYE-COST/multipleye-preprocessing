"""Pydantic models for the review web API."""

from typing import Literal

from pydantic import BaseModel, Field


ReviewStatus = Literal["unreviewed", "accepted", "flagged", "excluded"]
CheckStatus = Literal["pass", "warn", "fail"]


class CheckResult(BaseModel):
    check_id: str = Field(description="Unique identifier for the check")
    label: str = Field(description="Human-readable name")
    value: str | float | int | bool | None = Field(description="The raw value")
    threshold: str | list[float | int] | None = Field(
        description="Expected range or value"
    )
    status: CheckStatus = Field(description="pass / warn / fail")


class ReviewAnnotation(BaseModel):
    status: ReviewStatus = Field(default="unreviewed")
    reviewer: str = Field(
        default="", description="Reviewer name, auto-populated from cookie"
    )
    comment: str = Field(default="")
    reviewed_at: str | None = Field(
        default=None, description="ISO timestamp, auto-set on save"
    )


class SessionSummary(BaseModel):
    sid: str
    pid: int
    is_pilot: bool
    n_flags: int = 0
    n_fail_flags: int = 0
    n_warn_flags: int = 0
    review_status: ReviewStatus = "unreviewed"
    reviewer: str = ""


class SessionDetail(BaseModel):
    sid: str
    pid: int
    is_pilot: bool
    overview: dict = Field(
        default_factory=dict, description="All fields from overview YAML"
    )
    checks: list[CheckResult] = Field(default_factory=list)
    review: ReviewAnnotation = Field(default_factory=ReviewAnnotation)
    plots_available: bool = False


class DcnSummary(BaseModel):
    dcn_name: str
    language: str = ""
    country: str = ""
    year: str = ""
    n_sessions: int = 0
    n_pilots: int = 0
    is_processed: bool = False
    n_reviewed_unreviewed: int = 0
    n_reviewed_accepted: int = 0
    n_reviewed_flagged: int = 0
    n_reviewed_excluded: int = 0


class FlagSummary(BaseModel):
    flag_id: str
    label: str
    n_sessions_affected: int = 0
    severity: CheckStatus = "fail"
