"""Frekwencja: testy uprawnień i braku nadpisywania ocen."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "attendance-test-secret-at-least-32-chars"

import pytest
from app import app
from models import db, Student, Subject, TeacherAssignment, User, Grade
from attendance_models import Attendance


@pytest.fixture
def context():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        ala = Student(first_name="Ala", last_name="Test", school_class="1A")
        ola = Student(first_name="Ola", last_name="Test", school_class="2B")
        math = Subject(name="Matematyka")
        history = Subject(name="Historia")
        teacher = User(username="attendance_teacher", role="teacher")
        pupil = User(username="attendance_pupil", role="student")
        admin = User(username="attendance_admin", role="admin")
        for user in [teacher, pupil, admin]:
            user.set_password("attendance-test-password-123")
        db.session.add_all([ala, ola, math, history, teacher, pupil, admin])
        db.session.flush()
        pupil.student_id = ala.id
        db.session.add(TeacherAssignment(teacher_id=teacher.id, subject_id=math.id,
                                         school_class="1A"))
        db.session.add(Grade(student_id=ala.id, subject_id=math.id, value=5))
        db.session.commit()
        ids = dict(ala=ala.id, ola=ola.id, math=math.id, history=history.id)
        with app.test_client() as client:
            yield client, ids
        db.session.remove()
        db.drop_all()


def login(client, name):
    response = client.post('/login', data={
        'username': name, 'password': 'attendance-test-password-123'})
    assert response.status_code == 302


def form(ids):
    return {'school_class': '1A', 'subject_id': str(ids['math']),
            'date': '2026-11-03', f"status_{ids['ala']}": 'absent'}


def test_teacher_marks_and_updates_without_duplicate(context):
    client, ids = context
    login(client, 'attendance_teacher')
    assert client.get('/teacher/attendance').status_code == 200
    response = client.get('/teacher/attendance', query_string={
        'school_class': '1A', 'subject_id': ids['math'], 'date': '2026-11-03'})
    assert response.status_code == 200
    assert 'Ala' in response.get_data(as_text=True)
    assert client.post('/teacher/attendance', data=form(ids)).status_code == 302
    with app.app_context():
        assert Attendance.query.one().status == 'absent'
        assert Grade.query.count() == 1
    changed = {**form(ids), f"status_{ids['ala']}": 'late'}
    assert client.post('/teacher/attendance', data=changed).status_code == 302
    with app.app_context():
        assert Attendance.query.count() == 1
        assert Attendance.query.one().status == 'late'


def test_teacher_cannot_edit_other_class_or_subject(context):
    client, ids = context
    login(client, 'attendance_teacher')
    assert client.post('/teacher/attendance', data={**form(ids),
        'school_class': '2B', f"status_{ids['ola']}": 'absent'}).status_code == 403
    assert client.post('/teacher/attendance', data={**form(ids),
        'subject_id': str(ids['history'])}).status_code == 403
    assert client.post('/teacher/attendance', data={**form(ids),
        f"status_{ids['ola']}": 'absent'}).status_code == 400
    assert client.post('/teacher/attendance', data={**form(ids),
        f"status_{ids['ala']}": 'invalid'}).status_code == 400
    with app.app_context():
        assert Attendance.query.count() == 0


def test_student_sees_only_own_attendance(context):
    client, ids = context
    with app.app_context():
        db.session.add_all([
            Attendance(student_id=ids['ala'], subject_id=ids['math'],
                       lesson_date=__import__('datetime').date(2026, 11, 3), status='present'),
            Attendance(student_id=ids['ola'], subject_id=ids['history'],
                       lesson_date=__import__('datetime').date(2026, 11, 3), status='absent')])
        db.session.commit()
    login(client, 'attendance_pupil')
    response = client.get('/student/attendance')
    assert response.status_code == 200
    assert 'Matematyka' in response.get_data(as_text=True)
    assert 'Historia' not in response.get_data(as_text=True)
    assert client.get('/teacher/attendance').status_code == 403
    assert client.post('/teacher/attendance', data=form(ids)).status_code == 403


def test_admin_has_no_teacher_permissions(context):
    client, ids = context
    login(client, 'attendance_admin')
    assert client.get('/teacher/attendance').status_code == 403
    assert client.get('/student/attendance').status_code == 403
