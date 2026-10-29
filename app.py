
from flask import Flask, render_template, request, redirect, url_for, flash

from config import Config
from models import db, Student, Subject, Grade

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "dev-only-change-before-production"

db.init_app(app)


@app.route("/")
def home():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
