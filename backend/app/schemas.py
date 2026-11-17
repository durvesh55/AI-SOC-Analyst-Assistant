"""Pydantic request models: every piece of client input is validated here."""
import ipaddress
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from .security import MAX_PASSWORD_BYTES

Severity = Literal["Critical", "High", "Medium", "Low"]
AlertStatus = Literal["New", "Under Investigation", "Resolved", "False Positive"]
CaseWorkStatus = Literal["Open", "In Progress"]
Role = Literal["Admin", "Analyst"]
Category = Literal[
    "Malware", "Phishing", "Brute Force", "Suspicious Login", "Network Intrusion",
    "Web Attack", "Data Exfiltration", "Privilege Escalation", "Denial of Service",
    "Policy Violation", "Other",
]

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


def _check_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ValueError("Password must contain at least one letter and one digit")
    return value


class _PasswordMixin(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)


# ---------- auth / users ----------
class RegisterRequest(_PasswordMixin):
    username: str
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def valid_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("Username must be 3-30 chars: letters, digits, '_', '.', '-'")
        return v.lower()


class AdminCreateUser(RegisterRequest):
    role: Role = "Analyst"


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=254, description="Username or email")
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    email: Optional[EmailStr] = None


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return _check_password(v)


class AdminUserUpdate(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=80)


# ---------- alerts ----------
def _check_ip(v: Optional[str]) -> Optional[str]:
    if v in (None, ""):
        return None
    try:
        return str(ipaddress.ip_address(v.strip()))
    except ValueError:
        raise ValueError("Must be a valid IPv4/IPv6 address")


class AlertBase(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    severity: Severity
    category: Category
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    hostname: Optional[str] = Field(default=None, max_length=255)
    affected_user: Optional[str] = Field(default=None, max_length=100)
    indicators: list[str] = Field(default_factory=list, max_length=20)
    event_time: Optional[datetime] = None

    @field_validator("source_ip", "destination_ip")
    @classmethod
    def valid_ip(cls, v):
        return _check_ip(v)

    @field_validator("indicators")
    @classmethod
    def indicator_len(cls, v: list[str]) -> list[str]:
        cleaned = [i.strip() for i in v if i and i.strip()]
        if any(len(i) > 200 for i in cleaned):
            raise ValueError("Each indicator must be at most 200 characters")
        return cleaned


class AlertCreate(AlertBase):
    assigned_to: Optional[str] = None


class AlertUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    severity: Optional[Severity] = None
    category: Optional[Category] = None
    status: Optional[AlertStatus] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    hostname: Optional[str] = Field(default=None, max_length=255)
    affected_user: Optional[str] = Field(default=None, max_length=100)
    indicators: Optional[list[str]] = Field(default=None, max_length=20)

    @field_validator("source_ip", "destination_ip")
    @classmethod
    def valid_ip(cls, v):
        return _check_ip(v)


class AssignRequest(BaseModel):
    assignee_id: Optional[str] = Field(default=None, description="User id, or null to unassign")


# ---------- cases ----------
class CaseCreate(BaseModel):
    alert_ids: list[str] = Field(min_length=1, max_length=20)
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    assignee_id: Optional[str] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    severity: Optional[Severity] = None
    status: Optional[CaseWorkStatus] = None
    findings: Optional[str] = Field(default=None, max_length=10000)
    conclusion: Optional[str] = Field(default=None, max_length=10000)


class NoteCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class CaseClose(BaseModel):
    conclusion: str = Field(min_length=5, max_length=10000)
    outcome: Literal["Resolved", "False Positive"]


class CaseReopen(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
