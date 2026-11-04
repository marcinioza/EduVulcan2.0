"""Pliki planow lekcji przypisane do klas. PDF przechowywany w MySQL."""
from datetime import datetime, timezone
from models import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ClassTimetable(db.Model):
    __tablename__ = 'class_timetables'
    id = db.Column(db.Integer, primary_key=True)
    school_class = db.Column(db.String(30), unique=True, nullable=False)
    filename = db.Column(db.String(180), nullable=False)
    content = db.Column(db.LargeBinary(length=2 * 1024 * 1024), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
