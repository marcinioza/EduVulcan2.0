
import os

from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from flask_login import LoginManager
from models import User

from config import Config
from models import db, Student, Subject, Grade

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-only-change-before-production"
)

db.init_app(app)

# Konfiguracja systemu logowania
login_manager = LoginManager()
login_manager.init_app(app)

# Strona, na którą trafiają niezalogowani użytkownicy
login_manager.login_view = "login"
login_manager.login_message = "Zaloguj się, aby kontynuować."
login_manager.login_message_category = "error"


# Odczytywanie użytkownika z sesji
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None



@app.route("/")
def home():
    student_count = db.session.query(Student).count()
    grade_count = db.session.query(Grade).count()
    subject_count = db.session.query(Subject).count()

    average_grade = db.session.query(
        db.func.avg(Grade.value)
    ).scalar()

    recent_grades = Grade.query.order_by(
        Grade.created_at.desc(),
        Grade.id.desc()
    ).limit(5).all()

    return render_template(
        "index.html",
        student_count=student_count,
        grade_count=grade_count,
        subject_count=subject_count,
        average_grade=average_grade,
        recent_grades=recent_grades
    )



@app.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        school_class = request.form.get("school_class", "").strip()

        if not first_name or not last_name or not school_class:
            flash("Wszystkie pola są wymagane.", "error")

        elif (
            len(first_name) > 100
            or len(last_name) > 100
            or len(school_class) > 30
        ):
            flash("Przekroczono dozwoloną długość pola.", "error")

        else:
            student = Student(
                first_name=first_name,
                last_name=last_name,
                school_class=school_class
            )

            db.session.add(student)
            db.session.commit()

            flash("Uczeń został dodany pomyślnie.", "success")
            return redirect(url_for("students"))

    all_students = Student.query.order_by(
        Student.last_name,
        Student.first_name
    ).all()

    return render_template("students.html", students=all_students)


@app.route("/subjects", methods=["GET", "POST"])
def subjects():
    if request.method == "POST":
        name = request.form.get("name", "").strip()

        if not name:
            flash("Podaj nazwę przedmiotu.", "error")

        elif len(name) > 100:
            flash("Nazwa przedmiotu jest za długa.", "error")

        else:
            existing = Subject.query.filter(
                func.lower(Subject.name) == name.lower()
            ).first()

            if existing:
                flash("Taki przedmiot już istnieje.", "error")
            else:
                subject = Subject(name=name)
                db.session.add(subject)

                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    flash("Nie udało się dodać przedmiotu.", "error")
                else:
                    flash("Przedmiot został dodany.", "success")
                    return redirect(url_for("subjects"))

    all_subjects = Subject.query.order_by(Subject.name).all()

    return render_template(
        "subjects.html",
        subjects=all_subjects
    )

@app.route("/grades", methods=["GET", "POST"])
def grades():
    if request.method == "POST":
        student_id = request.form.get("student_id", "")
        subject_id = request.form.get("subject_id", "")
        value = request.form.get("value", "")

        if not student_id.isdigit() or not subject_id.isdigit():
            flash("Wybierz poprawnego ucznia i przedmiot.", "error")

        elif value not in {"1", "2", "3", "4", "5", "6"}:
            flash("Ocena musi być liczbą od 1 do 6.", "error")

        else:
            student = db.session.get(Student, int(student_id))
            subject = db.session.get(Subject, int(subject_id))

            if student is None or subject is None:
                flash("Wybrany uczeń lub przedmiot nie istnieje.", "error")

            else:
                new_grade = Grade(
                    student_id=student.id,
                    subject_id=subject.id,
                    value=int(value)
                )

                db.session.add(new_grade)
                db.session.commit()

                flash("Ocena została dodana pomyślnie.", "success")
                return redirect(url_for("grades"))

    all_students = Student.query.order_by(
        Student.last_name, Student.first_name
    ).all()

    all_subjects = Subject.query.order_by(
        Subject.name
    ).all()

    all_grades = Grade.query.order_by(
        Grade.created_at.desc(), Grade.id.desc()
    ).all()

    return render_template(
        "grades.html",
        students=all_students,
        subjects=all_subjects,
        grades=all_grades
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
