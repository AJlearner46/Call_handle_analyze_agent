from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.db import models


def list_doctors(db: Session, specialization: str | None = None) -> list[models.Doctor]:
    query = db.query(models.Doctor)
    if specialization:
        query = query.filter(models.Doctor.specialization == specialization)
    return query.all()


def get_slots(db: Session, doctor_id: int, target_date: date) -> list[str]:
    start = datetime.combine(target_date, time(hour=9))
    end = datetime.combine(target_date, time(hour=17))

    appointments = (
        db.query(models.Appointment)
        .filter(models.Appointment.doctor_id == doctor_id)
        .filter(models.Appointment.slot_time >= start)
        .filter(models.Appointment.slot_time < end)
        .all()
    )
    booked = {appt.slot_time for appt in appointments}

    slots = []
    current = start
    while current < end:
        if current not in booked:
            slots.append(current.strftime("%Y-%m-%d %H:%M"))
        current += timedelta(minutes=30)

    return slots


def book_appointment(db: Session, payload: dict) -> models.Appointment:
    appointment = models.Appointment(**payload)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: int) -> bool:
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if not appointment:
        return False
    appointment.status = "cancelled"
    db.commit()
    return True


def find_appointments_by_phone(db: Session, phone: str) -> list[models.Appointment]:
    return (
        db.query(models.Appointment)
        .filter(models.Appointment.phone == phone)
        .filter(models.Appointment.status == "booked")
        .all()
    )


def find_appointment_by_details(
    db: Session, phone: str | None, doctor_id: int | None, slot_time: datetime | None
) -> models.Appointment | None:
    query = db.query(models.Appointment).filter(models.Appointment.status == "booked")
    if phone:
        query = query.filter(models.Appointment.phone == phone)
    if doctor_id:
        query = query.filter(models.Appointment.doctor_id == doctor_id)
    if slot_time:
        query = query.filter(models.Appointment.slot_time == slot_time)
    return query.first()
