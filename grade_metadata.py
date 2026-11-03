"""Metadane ocen: nie zmieniają istniejącej tabeli grades."""
from models import db

GRADE_KINDS = {
    "sprawdzian": ("Sprawdzian", "red"),
    "kartkowka": ("Kartkówka", "orange"),
    "zadanie": ("Zadanie domowe", "blue"),
    "aktywnosc": ("Aktywność", "green"),
    "odpowiedz": ("Odpowiedź", "purple"),
    "inne": ("Inne", "gray"),
}


class GradeMetadata(db.Model):
    __tablename__ = "grade_metadata"
    grade_id = db.Column(db.Integer, db.ForeignKey("grades.id"), primary_key=True)
    kind = db.Column(db.String(20), nullable=False, default="inne")
    description = db.Column(db.String(120), nullable=False, default="")
    grade = db.relationship("Grade", backref=db.backref("metadata_entry", uselist=False))
