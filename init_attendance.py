"""Bezpieczna, powtarzalna migracja: tylko CREATE TABLE IF NOT EXISTS."""
from app import app
from models import db
from attendance_models import Attendance

with app.app_context():
    Attendance.__table__.create(bind=db.engine, checkfirst=True)
    print("Tabela attendance gotowa. Uczniowie i oceny pozostają bez zmian.")
