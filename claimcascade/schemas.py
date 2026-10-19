from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(StrictModel):
    claim_id: str = Field(min_length=1, max_length=100)
    business_name: str = Field(min_length=1)
    notification_timestamp: datetime
    incident_start: datetime | None = None
    incident_end: datetime | None = None
    x: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    y: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    business_type: str
    loss_type: str
    narrative: str = Field(min_length=1, max_length=10000)
    reported_amount_gbp: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)

    @field_validator("notification_timestamp", "incident_start", "incident_end")
    @classmethod
    def timezone_required(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError("Timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def interval(self):
        if self.incident_end and not self.incident_start:
            raise ValueError("incident_end requires incident_start")
        if self.incident_start and self.incident_end and self.incident_end < self.incident_start:
            raise ValueError("Incident interval is reversed")
        if (self.x is None) != (self.y is None):
            raise ValueError("Supply both coordinates or neither")
        return self


class Bulletin(StrictModel):
    bulletin_id: str
    start: datetime
    end: datetime
    x: float = Field(ge=0, le=100, allow_inf_nan=False)
    y: float = Field(ge=0, le=100, allow_inf_nan=False)
    radius_km: float = Field(gt=0, le=150, allow_inf_nan=False)
    description: str

    @model_validator(mode="after")
    def interval(self):
        if self.start.utcoffset() is None or self.end.utcoffset() is None or self.end < self.start:
            raise ValueError("Bulletin requires an ordered timezone-aware interval")
        return self


class Settings(StrictModel):
    distance_km: float = Field(default=10, gt=0, le=150)
    time_gap_hours: float = Field(default=24, ge=0, le=720)


class Evidence(StrictModel):
    claim_id: str
    excerpt: str = Field(min_length=1)


class Fact(StrictModel):
    claim_id: str
    kind: Literal["cause", "timing", "asset", "wider_event", "conflict"]
    value: str
    excerpt: str = Field(min_length=1)


class Extraction(StrictModel):
    facts: list[Fact]


class Cluster(StrictModel):
    cluster_id: str
    description: str
    members: list[str] = Field(min_length=2)
    evidence: list[Evidence]
    ambiguities: list[str] = []


class Proposals(StrictModel):
    clusters: list[Cluster]
    unassigned: list[str]


class Objection(StrictModel):
    cluster_id: str
    concern: str
    suggested_removals: list[str] = []
    suggested_splits: list[list[str]] = []


class Challenge(StrictModel):
    objections: list[Objection]


class Explanation(StrictModel):
    cluster_id: str
    observed_facts: list[str]
    hypotheses: list[str]
    missing_information: list[str]


class Report(StrictModel):
    explanations: list[Explanation]
