"""Bezpieczne, osobne widoki kont, nauczycieli i uczniów."""
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from models import db, Grade, Student, Subject, TeacherAssignment, User

role_bp = Blueprint("roles", __name__)


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def protected(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)
        return protected
    return decorator


@role_bp.route("/admin/users", methods=["GET", "POST"])
@role_required("admin")
def admin_users():
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create_user":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "")
            student_id_raw = request.form.get("student_id", "")
            if not 3 <= len(username) <= 80 or not username.replace("_", "").replace("-", "").isalnum():
                flash("Login: 3–80 znaków; tylko litery, cyfry, _ oraz -.", "error")
            elif not 12 <= len(password) <= 128:
                flash("Hasło musi mieć od 12 do 128 znaków.", "error")
            elif role not in {"teacher", "student"}:
                flash("Nieprawidłowa rola użytkownika.", "error")
            elif User.query.filter(func.lower(User.username) == username.lower()).first():
                flash("Taki login już istnieje.", "error")
            else:
                student_id = None
                if role == "student":
                    if not student_id_raw.isdigit():
                        flash("Wybierz ucznia dla konta uczniowskiego.", "error")
                        return redirect(url_for("roles.admin_users"))
                    student_id = int(student_id_raw)
                    student = db.session.get(Student, student_id)
                    if not student or User.query.filter_by(student_id=student_id).first():
                        flash("Nieprawidłowy uczeń lub konto już istnieje.", "error")
                        return redirect(url_for("roles.admin_users"))
                user = User(username=username, role=role, student_id=student_id)
                user.set_password(password)
                db.session.add(user)
                try:
                    db.session.commit()
                    flash("Konto zostało utworzone.", "success")
                except IntegrityError:
                    db.session.rollback()
                    flash("Nie udało się utworzyć konta; sprawdź login i ucznia.", "error")

        elif action == "assign":
            teacher_id = request.form.get("teacher_id", "")
            subject_id = request.form.get("subject_id", "")
            school_class = request.form.get("school_class", "").strip()
            classes = {name for (name,) in db.session.query(Student.school_class).distinct().all()}
            teacher = db.session.get(User, int(teacher_id)) if teacher_id.isdigit() else None
            subject = db.session.get(Subject, int(subject_id)) if subject_id.isdigit() else None
            if not teacher or teacher.role != "teacher" or not subject or school_class not in classes:
                flash("Wybierz poprawnego nauczyciela, przedmiot i klasę.", "error")
            elif TeacherAssignment.query.filter_by(teacher_id=teacher.id, subject_id=subject.id, school_class=school_class).first():
                flash("Takie przypisanie już istnieje.", "error")
            else:
                db.session.add(TeacherAssignment(teacher_id=teacher.id, subject_id=subject.id, school_class=school_class))
                try:
                    db.session.commit()
                    flash("Przydział został zapisany.", "success")
                except IntegrityError:
                    db.session.rollback()
                    flash("Nie udało się dodać przydziału.", "error")

        elif action == "remove_assignment":
            assignment_id = request.form.get("assignment_id", "")
            assignment = db.session.get(TeacherAssignment, int(assignment_id)) if assignment_id.isdigit() else None
            if not assignment:
                abort(404)
            db.session.delete(assignment)
            db.session.commit()
            flash("Przydział został usunięty. Istniejące oceny zachowano.", "success")
        else:
            abort(400)

        return redirect(url_for("roles.admin_users"))

    users = User.query.order_by(User.role, User.username).all()
    students = Student.query.order_by(Student.school_class, Student.last_name, Student.first_name).all()
    subjects = Subject.query.order_by(Subject.name).all()
    assignments = TeacherAssignment.query.order_by(TeacherAssignment.school_class, TeacherAssignment.subject_id).all()
    classes = sorted({student.school_class for student in students})
    return render_template("admin_users.html", users=users, students=students,
                           subjects=subjects, assignments=assignments, classes=classes)


@role_bp.route("/teacher", methods=["GET", "POST"])
@role_required("teacher")
def teacher_panel():
    assignments = TeacherAssignment.query.filter_by(teacher_id=current_user.id).all()
    allowed_pairs = {(a.school_class, a.subject_id) for a in assignments}
    classes = {a.school_class for a in assignments}
    subject_ids = {a.subject_id for a in assignments}

    if request.method == "POST":
        student_id = request.form.get("student_id", "")
        subject_id = request.form.get("subject_id", "")
        value = request.form.get("value", "")
        student = db.session.get(Student, int(student_id)) if student_id.isdigit() else None
        subject = db.session.get(Subject, int(subject_id)) if subject_id.isdigit() else None
        if not student or not subject or value not in {"1", "2", "3", "4", "5", "6"}:
            flash("Wybierz poprawnego ucznia, przedmiot i ocenę.", "error")
        elif (student.school_class, subject.id) not in allowed_pairs:
            abort(403)
        else:
            db.session.add(Grade(student_id=student.id, subject_id=subject.id, value=int(value)))
            db.session.commit()
            flash("Ocena została zapisana.", "success")
            return redirect(url_for("roles.teacher_panel"))

    students = Student.query.filter(Student.school_class.in_(classes)).order_by(Student.school_class, Student.last_name).all() if classes else []
    subjects = Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all() if subject_ids else []
    if allowed_pairs:
        conditions = [and_(Student.school_class == school_class, Grade.subject_id == subject_id)
                      for school_class, subject_id in allowed_pairs]
        grades = (Grade.query.join(Student, Grade.student_id == Student.id)
                  .filter(or_(*conditions)).order_by(Grade.created_at.desc(), Grade.id.desc())
                  .limit(100).all())
    else:
        grades = []
    return render_template("teacher.html", assignments=assignments, students=students,
                           subjects=subjects, grades=grades, allowed_pairs=allowed_pairs)


@role_bp.route("/student")
@role_required("student")
def student_panel():
    if current_user.student_id is None:
        abort(403)
    student = db.session.get(Student, current_user.student_id)
    if student is None:
        abort(403)
    grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.created_at.desc(), Grade.id.desc()).all()
    average = db.session.query(func.avg(Grade.value)).filter(Grade.student_id == student.id).scalar()
    return render_template("student.html", student=student, grades=grades, average=average)


# Nowe widoki dziennika klasowego i ocen szczegółowych.
from journal_views import register_journal
register_journal(role_bp, role_required)
