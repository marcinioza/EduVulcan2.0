"""Tworzy tylko nowa tabele class_timetables. Bez ingerencji w inne dane."""
from app import app
from models import db
from timetable_models import ClassTimetable

with app.app_context():
    ClassTimetable.__table__.create(bind=db.engine, checkfirst=True)
    print('Tabela class_timetables gotowa. Oceny, konta, frekwencja i wiadomości bez zmian.')
