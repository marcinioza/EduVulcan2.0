"""Testy dziennika klasowego i ochrony uprawnień. Uruchom: pytest -q"""
import os

os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'unit-test-only-secret-key-at-least-32-chars'

import pytest
from app import app
from models import db, Grade, Student, Subject, TeacherAssignment, User
from grade_metadata import GradeMetadata


@pytest.fixture
def setup_db():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        students = [Student(first_name='Anna', last_name='Demo', school_class='1A'),
                    Student(first_name='Jan', last_name='Demo', school_class='2B')]
        subjects = [Subject(name='Matematyka'), Subject(name='Historia')]
        users = [User(username='journal_teacher', role='teacher'),
                 User(username='journal_student', role='student')]
        for user in users:
            user.set_password('test-password-12345')
        db.session.add_all(students + subjects + users)
        db.session.flush()
        users[1].student_id = students[0].id
        db.session.add(TeacherAssignment(teacher_id=users[0].id, subject_id=subjects[0].id, school_class='1A'))
        db.session.commit()
        ids = {'anna': students[0].id, 'jan': students[1].id,
               'math': subjects[0].id, 'history': subjects[1].id}
        with app.test_client() as client:
            yield client, ids
        db.session.remove()
        db.drop_all()


def login(client, username):
    response = client.post('/login', data={'username': username, 'password': 'test-password-12345'})
    assert response.status_code == 302


def test_teacher_must_select_authorized_class(setup_db):
    client, ids = setup_db
    login(client, 'journal_teacher')
    assert client.get('/teacher/journal').status_code == 200
    assert client.get('/teacher/journal?class=1A').status_code == 200
    assert client.get('/teacher/journal?class=2B').status_code == 403
    assert client.get('/teacher/journal?class=1A').data.find(b'Matematyka') >= 0
    assert client.get('/teacher/journal?class=1A').data.find(b'Historia') < 0


def test_teacher_cannot_create_grade_for_other_class_or_subject(setup_db):
    client, ids = setup_db
    login(client, 'journal_teacher')
    base = dict(action='create', school_class='1A', student_id=str(ids['anna']),
                subject_id=str(ids['math']), value='5', kind='sprawdzian', description='Test')
    assert client.post('/teacher/journal', data=base).status_code == 302
    with app.app_context():
        grade = Grade.query.one()
        assert db.session.get(GradeMetadata, grade.id).description == 'Test'
    assert client.post('/teacher/journal', data={**base, 'student_id': str(ids['jan'])}).status_code == 400
    assert client.post('/teacher/journal', data={**base, 'subject_id': str(ids['history'])}).status_code == 403
    assert client.post('/teacher/journal', data={**base, 'kind': 'hacked'}).status_code == 400
    with app.app_context():
        assert Grade.query.count() == 1


def test_teacher_can_update_and_delete_owned_class_grade(setup_db):
    client, ids = setup_db
    login(client, 'journal_teacher')
    with app.app_context():
        grade = Grade(student_id=ids['anna'], subject_id=ids['math'], value=3)
        db.session.add(grade)
        db.session.commit()
        grade_id = grade.id
    base = dict(school_class='1A', grade_id=str(grade_id))
    assert client.post('/teacher/journal', data={**base, 'action': 'update',
        'value':'6', 'kind':'aktywnosc', 'description':'Dobra praca'}).status_code == 302
    with app.app_context():
        assert Grade.query.one().value == 6
        assert db.session.get(GradeMetadata, grade_id).kind == 'aktywnosc'
    assert client.post('/teacher/journal', data={**base, 'action':'delete'}).status_code == 302
    with app.app_context():
        assert Grade.query.count() == 0
        assert GradeMetadata.query.count() == 0


def test_student_reads_only_own_grade(setup_db):
    client, ids = setup_db
    with app.app_context():
        db.session.add_all([
            Grade(student_id=ids['anna'], subject_id=ids['math'], value=5),
            Grade(student_id=ids['jan'], subject_id=ids['history'], value=2)])
        db.session.commit()
    login(client, 'journal_student')
    response = client.get('/student/grades')
    assert response.status_code == 200
    assert b'Matematyka' in response.data
    assert b'Historia' not in response.data
    assert client.get('/teacher/journal').status_code == 403
