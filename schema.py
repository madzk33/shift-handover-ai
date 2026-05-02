"""Pydantic v2 models for structured shift handover documents."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """Issue severity level."""
    low = "low"
    medium = "medium"
    high = "high"


class EquipmentStatus(str, Enum):
    """Operational status of a piece of equipment."""
    ok = "ok"
    degraded = "degraded"
    down = "down"


class Issue(BaseModel):
    """A single issue raised during the shift."""
    severity: Severity
    description: str
    action_needed: str


class PendingItem(BaseModel):
    """An action item carried forward to the next shift."""
    item: str
    owner_next_shift: str
    deadline: str


class EquipmentReport(BaseModel):
    """Status snapshot for a piece of equipment or asset."""
    equipment: str
    status: EquipmentStatus
    notes: str


class Handover(BaseModel):
    """Complete structured handover document for one shift."""
    shift_date: str = Field(description="ISO-8601 date string, e.g. 2025-01-15")
    shift_type: Literal["Day", "Evening", "Night"]
    operative: str
    line_or_area: str
    summary: str = Field(description="2-3 sentence plain-English summary of the shift")
    issues_raised: list[Issue] = Field(default_factory=list)
    pending_items: list[PendingItem] = Field(default_factory=list)
    equipment_status: list[EquipmentReport] = Field(default_factory=list)
    stock_or_ingredient_notes: list[str] = Field(default_factory=list)
    safety_or_compliance_flags: list[str] = Field(default_factory=list)
    next_shift_priorities: list[str] = Field(
        default_factory=list,
        description="Top priorities for the incoming shift, maximum 3, ranked",
    )

    @field_validator("next_shift_priorities")
    @classmethod
    def cap_priorities(cls, v: list[str]) -> list[str]:
        """Ensure no more than three next-shift priorities are listed."""
        if len(v) > 3:
            raise ValueError("next_shift_priorities must contain at most 3 items")
        return v

    @field_validator("shift_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Loosely validate that the date looks like an ISO date."""
        parts = v.split("-")
        if len(parts) != 3 or len(parts[0]) != 4:
            raise ValueError(f"shift_date must be ISO-8601 format (YYYY-MM-DD), got: {v}")
        return v
