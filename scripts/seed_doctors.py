from app.db.database import SessionLocal, engine
from app.db.models import Base, Doctor

Base.metadata.create_all(bind=engine)

db = SessionLocal()

if not db.query(Doctor).first():
    doctors = [
        Doctor(name="Mehta", specialization="cardiologist", hospital="City Hospital"),
        Doctor(name="Shah", specialization="dermatologist", hospital="Green Clinic"),
        Doctor(name="Patel", specialization="neurologist", hospital="Metro Health"),
    ]
    db.add_all(doctors)
    db.commit()

print("Seed complete")
