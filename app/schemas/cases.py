"""Typed request and response models (NFR-SEC-04: strict input validation)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.states import AlertStatus, RecoveryStatus, ReportType


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in_minutes: int


class AlertStatusRequest(BaseModel):
    status: AlertStatus
    note: str = Field(min_length=1, max_length=1000)


class ReportCreate(BaseModel):
    plate_no: str = Field(pattern=r"^[A-Za-z0-9]{6,12}$")
    report_type: ReportType
    fir_ref: str = Field(min_length=1, max_length=50)
    reported_place: str = Field(min_length=1, max_length=200)
    reported_at: datetime | None = None


class ReportStatusRequest(BaseModel):
    status: RecoveryStatus
    note: str = Field(min_length=1, max_length=1000)
    location: str | None = Field(default=None, max_length=200)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    alert_id: str
    alert_type: str
    severity: str
    plate_no: str
    status: str
    station_id: str
    merged_count: int
    created_at: datetime


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    report_id: str
    plate_no: str
    report_type: str
    fir_ref: str
    reported_place: str
    reported_at: datetime
    recovery_status: str
    updated_at: datetime
