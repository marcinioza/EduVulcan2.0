"""Dodaje fikcyjne dane demonstracyjne EduVulcan2.0.

Nie usuwa ani nie aktualizuje istniejących rekordów.
Ponowne uruchomienie pomija już dodane dane.
Wymaga istniejącej tabeli teacher_assignments (init_roles.py).
"""
from datetime import datetime
from secrets import token_urlsafe

from sqlalchemy import func

from app import app
from models import db, Grade, Student, Subject, TeacherAssignment, User


CLASSES = {
    "1TI-DEMO": [
        ("Anna", "Nowicka"),
        ("Jakub", "Zieliński"),
        ("Maja", "Wiśniewska"),
        ("Filip", "Kamiński"),
    ],
    "2TI-DEMO": [
        ("Zofia", "Lewandowska"),
        ("Adam", "Kowalski"),
        ("Lena", "Mazur"),
        ("Michał", "Wójcik"),
    ],
    "3TI-DEMO": [
        ("Julia", "Szymańska"),
        ("Kacper", "Dąbrowski"),
        ("Oliwia", "Król"),
        ("Piotr", "Pawlak"),
    ],
}

SUBJECTS = [
    "Matematyka",
    "Język polski",
    "Język angielski",
    "Informatyka",
    "Historia",
]

# Login nauczyciela -> przedmioty, do których go przypisujemy.
TEACHERS = {
    "demo_nauczyciel_matematyka": ["Matematyka", "Informatyka"],
    "demo_nauczyciel_polski": ["Język polski", "Historia"],
    "demo_nauczyciel_angielski": ["Język angielski"],
}

# Dla przykładu tworzymy również konta trzech uczniów.
STUDENT_LOGINS = {
    ("Anna", "Nowicka", "1TI-DEMO"): "demo_uczen_anna",
    ("Zofia", "Lewandowska", "2TI-DEMO"): "demo_uczen_zofia",
    ("Julia", "Szymańska", "3TI-DEMO"): "demo_uczen_julia",
}


def create_user(username, role, student_id=None):
    existing = User.query.filter(func.lower(User.username) == username.lower()).first()
    if existing:
        if existing.role != role or existing.student_id != student_id:
            raise ValueError(f"Login '{username}' jest już zajęty przez inne konto.")
        return existing, None

    if student_id is not None and User.query.filter_by(student_id=student_id).first():
        raise ValueError(f"Uczeń ID={student_id} ma już konto.")

    password = token_urlsafe(18)
    user = User(username=username, role=role, student_id=student_id)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user, password


def seed():
    passwords = []
    counts = dict(students=0, subjects=0, teachers=0, learners=0,
                  assignments=0, grades=0)

    with app.app_context():
        try:
            subjects = {}
            for subject_name in SUBJECTS:
                subject = Subject.query.filter(
                    func.lower(Subject.name) == subject_name.lower()
                ).first()
                if subject is None:
                    subject = Subject(name=subject_name)
                    db.session.add(subject)
                    db.session.flush()
                    counts["subjects"] += 1
                subjects[subject_name] = subject

            students = {}
            for school_class, names in CLASSES.items():
                for first_name, last_name in names:
                    student = Student.query.filter_by(
                        first_name=first_name,
                        last_name=last_name,
                        school_class=school_class,
                    ).first()
                    if student is None:
                        student = Student(
                            first_name=first_name,
                            last_name=last_name,
                            school_class=school_class,
                        )
                        db.session.add(student)
                        db.session.flush()
                        counts["students"] += 1
                    students[(first_name, last_name, school_class)] = student

            teachers = {}
            for username in TEACHERS:
                user, password = create_user(username, "teacher")
                teachers[username] = user
                if password:
                    passwords.append((username, password))
                    counts["teachers"] += 1

            for key, username in STUDENT_LOGINS.items():
                student = students[key]
                user, password = create_user(username, "student", student.id)
                if password:
                    passwords.append((username, password))
                    counts["learners"] += 1

            for username, subject_names in TEACHERS.items():
                for school_class in CLASSES:
                    for subject_name in subject_names:
                        existing = TeacherAssignment.query.filter_by(
                            teacher_id=teachers[username].id,
                            subject_id=subjects[subject_name].id,
                            school_class=school_class,
                        ).first()
                        if existing is None:
                            db.session.add(TeacherAssignment(
                                teacher_id=teachers[username].id,
                                subject_id=subjects[subject_name].id,
                                school_class=school_class,
                            ))
                            counts["assignments"] += 1

            # Oceny są tworzone tylko, gdy uczeń nie ma jeszcze oceny
            # z danego przedmiotu. Nie nadpisujemy istniejących ocen.
            for index, student in enumerate(students.values()):
                for offset, subject_name in enumerate(SUBJECTS):
                    subject = subjects[subject_name]
                    existing = Grade.query.filter_by(
                        student_id=student.id,
                        subject_id=subject.id,
                    ).first()
                    if existing is None:
                        value = 2 + ((index + offset * 2) % 5)
                        db.session.add(Grade(
                            student_id=student.id,
                            subject_id=subject.id,
                            value=value,
                            created_at=datetime(2026, 10, 5 + offset, 9, index),
                        ))
                        counts["grades"] += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    print("\nDodano nowe rekordy (pominięto już istniejące):")
    for name, count in counts.items():
        print(f"  {name}: {count}")

    if passwords:
        print("\nNOWE KONTA DEMO — hasła pojawią się tylko teraz.")
        print("Zapisz je prywatnie. Nie publikuj, nie rób zrzutów ekranu.")
        for username, password in passwords:
            print(f"  {username}: {password}")
        print("Zmień hasła, jeśli konta miałyby być używane poza testami.")
    else:
        print("\nNie utworzono nowych kont; istniejących haseł nie zmieniono.")


if __name__ == "__main__":
    seed()
