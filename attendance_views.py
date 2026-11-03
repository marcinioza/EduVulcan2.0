"""Frekwencja na lekcjach: tylko przydzielony nauczyciel zapisuje; uczeń czyta swoje."""
from datetime import date
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from models import db, Student, Subject, TeacherAssignment
from attendance_models import Attendance, STATUSES


def _require_role(role):
    if current_user.role != role:
        abort(403)


def _parse_date(raw):
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        abort(400, "Niepoprawna data.")


def register_attendance(role_bp):
    @role_bp.route("/teacher/attendance", methods=["GET", "POST"])
    @login_required
    def teacher_attendance():
        _require_role("teacher")
        assignments = TeacherAssignment.query.filter_by(teacher_id=current_user.id).all()
        allowed = {(a.school_class, a.subject_id) for a in assignments}
        classes = sorted({a.school_class for a in assignments})
        is_post = request.method == "POST"
        params = request.form if is_post else request.args
        school_class = params.get("school_class", "").strip()
        subject_id_raw = params.get("subject_id", "")
        selected_date = params.get("date", date.today().isoformat())
        lesson_date = _parse_date(selected_date)

        if school_class and school_class not in classes:
            abort(403)
        subject_id = int(subject_id_raw) if subject_id_raw.isdigit() else None
        subject_choices = sorted(
            ((a.subject_id, a.subject.name) for a in assignments if a.school_class == school_class),
            key=lambda item: item[1],
        )
        subject_choices = list(dict.fromkeys(subject_choices))
        if subject_id is not None and (school_class, subject_id) not in allowed:
            abort(403)

        students = []
        records = {}
        if school_class and subject_id is not None:
            students = Student.query.filter_by(school_class=school_class).order_by(
                Student.last_name, Student.first_name).all()
            student_ids = [s.id for s in students]
            if student_ids:
                records = {a.student_id: a for a in Attendance.query.filter(
                    Attendance.student_id.in_(student_ids),
                    Attendance.subject_id == subject_id,
                    Attendance.lesson_date == lesson_date,
                ).all()}

        if is_post:
            if not school_class or subject_id is None or not students:
                abort(400)
            # Nie można przesłać ID ucznia spoza wybranej klasy ani pominąć ucznia.
            expected = {str(s.id) for s in students}
            incoming = {k.removeprefix("status_") for k in request.form if k.startswith("status_")}
            if incoming != expected:
                abort(400, "Lista uczniów nie zgadza się z klasą.")
            for student in students:
                status = request.form.get(f"status_{student.id}")
                if status not in STATUSES:
                    abort(400, "Niepoprawny status obecności.")
            for student in students:
                status = request.form[f"status_{student.id}"]
                record = records.get(student.id)
                if record is None:
                    db.session.add(Attendance(student_id=student.id, subject_id=subject_id,
                                              lesson_date=lesson_date, status=status))
                else:
                    record.status = status
            db.session.commit()
            flash("Frekwencja została zapisana.", "success")
            return redirect(url_for("roles.teacher_attendance", school_class=school_class,
                                    subject_id=subject_id, date=selected_date))

        return render_template("teacher_attendance.html", classes=classes,
                               school_class=school_class, subjects=subject_choices,
                               subject_id=subject_id, selected_date=selected_date,
                               students=students, records=records, statuses=STATUSES)


    @role_bp.route("/student/attendance")
    @login_required
    def student_attendance():
        _require_role("student")
        if current_user.student_id is None:
            abort(403)
        student = db.session.get(Student, current_user.student_id)
        if student is None:
            abort(403)
        entries = Attendance.query.filter_by(student_id=student.id).order_by(
            Attendance.lesson_date.desc(), Attendance.id.desc()).limit(200).all()
        summary = {key: sum(e.status == key for e in entries) for key in STATUSES}
        return render_template("student_attendance.html", student=student,
                               entries=entries, summary=summary, statuses=STATUSES)
