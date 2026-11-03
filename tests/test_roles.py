"""Security-focused tests run with temporary SQLite, never the school MySQL database."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "ci-only-unit-test-secret-key-123456789"

import pytest

from app import app
from models import db, Grade, Student, Subject, TeacherAssignment, User


@pytest.fixture
def client():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        s1 = Student(first_name="Ala", last_name="Testowa", school_class="1A")
        s2 = Student(first_name="Ola", last_name="Druga", school_class="2B")
        sub1 = Subject(name="Matematyka")
        sub2 = Subject(name="Historia")
        db.session.add_all([s1, s2, sub1, sub2])
        db.session.flush()
        db.session.add_all([
            Grade(student_id=s1.id, subject_id=sub1.id, value=5),
            Grade(student_id=s2.id, subject_id=sub2.id, value=2),
        ])
        for username, role, student in [
            ("admin", "admin", None),
            ("teacher", "teacher", None),
            ("learner", "student", s1.id),
        ]:
            user = User(username=username, role=role, student_id=student)
            user.set_password("correct-test-password-123")
            db.session.add(user)
        db.session.flush()
        teacher = User.query.filter_by(username="teacher").one()
        db.session.add(TeacherAssignment(teacher_id=teacher.id, subject_id=sub1.id, school_class="1A"))
        db.session.commit()
        with app.test_client() as test_client:
            yield test_client
        db.session.remove()
        db.drop_all()


def sign_in(client, username):
    response = client.post("/login", data={"username": username, "password": "correct-test-password-123"}, follow_redirects=False)
    assert response.status_code == 302


def test_guest_redirected(client):
    assert client.get("/").status_code == 302
    assert client.get("/teacher").status_code == 302
    assert client.get("/student").status_code == 302
    assert client.get("/admin/users").status_code == 302


def test_student_sees_only_own_grades(client):
    sign_in(client, "learner")
    body = client.get("/student").get_data(as_text=True)
    assert "Ala Testowa" in body
    assert "Matematyka" in body
    assert "Historia" not in body
    assert client.get("/grades").status_code == 403
    assert client.get("/teacher").status_code == 403
    assert client.get("/admin/users").status_code == 403


def test_teacher_can_grade_only_assigned_pair(client):
    sign_in(client, "teacher")
    body = client.get("/teacher").get_data(as_text=True)
    assert "Ala Testowa" in body
    assert "Ola Druga" not in body
    assert "Historia" not in body
    assert "Moja średnia" not in body
    assert client.post("/teacher", data={"student_id": "2", "subject_id": "2", "value": "6"}).status_code == 403
    assert client.post("/teacher", data={"student_id": "1", "subject_id": "2", "value": "6"}).status_code == 403
    assert client.post("/teacher", data={"student_id": "1", "subject_id": "1", "value": "6"}).status_code == 302
    assert client.get("/admin/users").status_code == 403
    assert client.get("/grades").status_code == 403


def test_admin_can_manage_accounts(client):
    sign_in(client, "admin")
    assert client.get("/").status_code == 200
    assert client.get("/admin/users").status_code == 200
    assert client.get("/student").status_code == 403
    assert client.post("/admin/users", data={"action": "create_user", "username": "teacher2", "password": "strong-password-123", "role": "teacher"}).status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="teacher2", role="teacher").one().check_password("strong-password-123")
