"""Jednorazowe, nieusuwające istniejących danych utworzenie tabeli przypisań.

Uruchom dopiero po wykonaniu kopii zapasowej:
    docker compose exec web python init_roles.py
"""
from app import app
from models import db, TeacherAssignment

with app.app_context():
    TeacherAssignment.__table__.create(bind=db.engine, checkfirst=True)
    print("Tabela teacher_assignments jest gotowa. Istniejące dane pozostają bez zmian.")
