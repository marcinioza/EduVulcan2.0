"""Uprawnienia do planow lekcji; migracja nie dotyka ocen ani wiadomosci."""
import os
from io import BytesIO
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'timetable-test-secret-key-long-enough'

import pytest
from app import app
from models import db, Student, Subject, TeacherAssignment, Grade, User
from timetable_models import ClassTimetable


@pytest.fixture
def client_db():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        first = Student(first_name='Anna', last_name='Demo', school_class='1A')
        second = Student(first_name='Ola', last_name='Demo', school_class='2B')
        subject = Subject(name='Matematyka')
        admin = User(username='plan_admin', role='admin')
        teacher = User(username='plan_teacher', role='teacher')
        pupil = User(username='plan_student', role='student')
        outsider = User(username='plan_outsider', role='student')
        for user in (admin, teacher, pupil, outsider):
            user.set_password('secret-test-password-123')
        db.session.add_all([first, second, subject, admin, teacher, pupil, outsider])
        db.session.flush()
        pupil.student_id = first.id
        outsider.student_id = second.id
        db.session.add(TeacherAssignment(teacher_id=teacher.id, subject_id=subject.id, school_class='1A'))
        db.session.add(Grade(student_id=first.id, subject_id=subject.id, value=5))
        db.session.commit()
        with app.test_client() as client:
            yield client
        db.session.remove()
        db.drop_all()


def login(client, who):
    assert client.post('/login', data={'username':who,'password':'secret-test-password-123'}).status_code == 302


def logout(client):
    assert client.post('/logout').status_code == 302


def upload(client, school_class, contents=b'%PDF-1.4\nhello\n%%EOF\n', name='plan.pdf'):
    return client.post('/timetables', data={'school_class':school_class, 'action':'upload',
        'file':(BytesIO(contents),name)}, content_type='multipart/form-data')


def test_admin_upload_replace_remove_without_touching_grades(client_db):
    client = client_db
    login(client, 'plan_admin')
    assert client.get('/timetables').status_code == 200
    assert upload(client,'1A').status_code == 302
    assert client.get('/timetables/download/1A').data.startswith(b'%PDF-')
    assert upload(client,'1A',b'%PDF-1.7\nnew\n%%EOF','nowy.pdf').status_code == 302
    with app.app_context():
        assert ClassTimetable.query.count() == 1
        assert ClassTimetable.query.one().filename == 'nowy.pdf'
        assert Grade.query.count() == 1
    assert client.post('/timetables',data={'school_class':'1A','action':'remove'}).status_code == 302
    with app.app_context():
        assert ClassTimetable.query.count() == 0
        assert Grade.query.count() == 1
    response=client.get('/timetables/download/1A')
    assert response.status_code == 200
    assert response.data.startswith(b'%PDF-')


def test_teacher_can_download_only_assigned_class(client_db):
    client = client_db
    login(client,'plan_teacher')
    assert client.get('/timetables').status_code == 200
    assert client.get('/timetables/download/1A').status_code == 200
    assert client.get('/timetables/download/2B').status_code == 403
    assert client.get('/timetables?school_class=2B').status_code == 403
    assert upload(client,'1A').status_code == 403


def test_student_only_own_class(client_db):
    client=client_db
    login(client,'plan_student')
    assert client.get('/timetables/download/1A').status_code == 200
    assert client.get('/timetables/download/2B').status_code == 403
    assert upload(client,'1A').status_code == 403
    logout(client)
    login(client,'plan_outsider')
    assert client.get('/timetables/download/2B').status_code == 200
    assert client.get('/timetables/download/1A').status_code == 403


def test_reject_invalid_pdfs_and_nonexisting_classes(client_db):
    client=client_db
    login(client,'plan_admin')
    assert upload(client,'1A',b'not pdf','bad.pdf').status_code == 400
    assert upload(client,'1A',b'%PDF-1.4\n%%EOF','bad.exe').status_code == 400
    assert upload(client,'1A',b'%PDF-' + b'x'*(2*1024*1024),'large.pdf').status_code == 413
    assert upload(client,'NONEXISTENT').status_code == 400
    with app.app_context():
        assert ClassTimetable.query.count() == 0


def test_guest_no_access(client_db):
    client=client_db
    assert client.get('/timetables').status_code==302
    assert client.get('/timetables/download/1A').status_code==302
