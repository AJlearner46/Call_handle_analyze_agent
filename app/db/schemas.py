from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DoctorOut(BaseModel):
    id: int
    name: str
    specialization: str
    hospital: Optional[str] = None


class AppointmentCreate(BaseModel):
    patient_name: str
    phone: str
    doctor_id: int
    slot_time: datetime


class AppointmentOut(BaseModel):
    id: int
    patient_name: str
    phone: str
    doctor_id: int
    slot_time: datetime
    status: str


class SlotResponse(BaseModel):
    doctor_id: int
    date: str
    slots: list[str]
