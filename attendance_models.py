"""Rejestr obecności uczniów na zajęciach (klasa wynika z ucznia)."""
from datetime import datetime, timezone
from models import db


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    lesson_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
                           onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    student = db.relationship("Student")
    subject = db.relationship("Subject")
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", "lesson_date", name="uq_attendance_student_subject_date"),
    )


STATUSES = {
    "present": ("Obecny", "green"),
    "absent": ("Nieobecny", "red"),
    "late": ("Spóźniony", "orange"),
    "excused": ("Usprawiedliwiony", "blue"),
}
