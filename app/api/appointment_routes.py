from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.schemas import AppointmentCreate, AppointmentOut, DoctorOut, SlotResponse
from app.services import appointment_service

router = APIRouter()


@router.get("/doctors", response_model=list[DoctorOut])
def get_doctors(specialization: str | None = None, db: Session = Depends(get_db)):
    doctors = appointment_service.list_doctors(db, specialization)
    return doctors


@router.get("/slots", response_model=SlotResponse)
def get_slots(doctor_id: int, date: str, db: Session = Depends(get_db)):
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format") from exc

    slots = appointment_service.get_slots(db, doctor_id, target_date)
    return SlotResponse(doctor_id=doctor_id, date=date, slots=slots)


@router.post("/appointments", response_model=AppointmentOut)
def book_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    appointment = appointment_service.book_appointment(db, payload.model_dump())
    return appointment


@router.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    success = appointment_service.cancel_appointment(db, appointment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "cancelled"}
