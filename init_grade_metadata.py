"""Bezpieczne utworzenie wyłącznie nowej tabeli grade_metadata."""
from app import app
from models import db
from grade_metadata import GradeMetadata

with app.app_context():
    GradeMetadata.__table__.create(bind=db.engine, checkfirst=True)
    print("Tabela grade_metadata gotowa. Dotychczasowe oceny zostały zachowane.")
