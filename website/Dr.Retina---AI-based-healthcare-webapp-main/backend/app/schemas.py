from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PatientIn(Input):
    fullName: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=120)
    gender: Literal["Female", "Male", "Other"]
    contactNumber: str = Field(default="", max_length=32)
    diabetesDurationYears: float = Field(default=0, ge=0, le=100)
    knownDiabetic: Literal["Yes", "No", "Unknown"] = "Unknown"
    campLocation: str = Field(default="", max_length=200)
    dateOfBirth: date | None = None
    address: str = Field(default="", max_length=500)
    clinicalHistory: str = Field(default="", max_length=4000)


class ReviewIn(Input):
    decision: Literal["VERIFIED", "ADDITIONAL_ANALYSIS_REQUIRED"]
    finalAssessment: str = Field(default="", max_length=4000)
    comments: str = Field(default="", max_length=4000)
    reason: (
        Literal[
            "IMAGE_QUALITY",
            "AI_UNCERTAIN",
            "ADDITIONAL_IMAGE",
            "ADDITIONAL_ANALYSIS",
            "CLINICAL_DISAGREEMENT",
            "OTHER",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def documented(self):
        if self.decision == "VERIFIED" and not self.finalAssessment:
            raise ValueError("A final clinical assessment is required")
        if self.decision == "ADDITIONAL_ANALYSIS_REQUIRED" and (not self.reason or not self.comments):
            raise ValueError("A reason and comments are required")
        return self


class OrganizationIn(Input):
    name: str = Field(min_length=2, max_length=200)
    type: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=2, max_length=500)
    contactEmail: EmailStr
    contactPhone: str = Field(default="", max_length=32)
    identifier: str = Field(min_length=2, max_length=80)


class InviteIn(Input):
    email: EmailStr
    fullName: str = Field(min_length=2, max_length=120)
    role: Literal["DOCTOR", "LAB_TECHNICIAN"]


class MemberUpdate(Input):
    active: bool
    role: Literal["DOCTOR", "LAB_TECHNICIAN"]
    available: bool = True


class AssignmentIn(Input):
    doctorId: UUID


class AvailabilityIn(Input):
    available: bool
