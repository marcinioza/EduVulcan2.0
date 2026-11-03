"""Tests for private inbox, groups, attachments, read state and trash."""
import os
from io import BytesIO
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['SECRET_KEY'] = 'test-messages-secret-key-at-least-32-characters'
import pytest
from app import app
from models import db, User, Student, Grade
from message_models import MailMessage, MailRecipient


@pytest.fixture
def mail_client():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.create_all()
        students = [Student(first_name='Ala',last_name='Testowa',school_class='1A'),
                    Student(first_name='Ola',last_name='Inna',school_class='2B')]
        db.session.add_all(students)
        db.session.flush()
        users = [User(username='mail_admin',role='admin'),
                 User(username='mail_teacher',role='teacher'),
                 User(username='mail_ala',role='student',student_id=students[0].id),
                 User(username='mail_ola',role='student',student_id=students[1].id)]
        for user in users:
            user.set_password('mail-password-12345')
        db.session.add_all(users)
        db.session.commit()
        ids={user.username:user.id for user in users}
        with app.test_client() as client:
            yield client,ids
        db.session.remove()
        db.drop_all()


def login(client, username):
    response=client.post('/login',data={'username':username,'password':'mail-password-12345'})
    assert response.status_code==302


def logout(client):
    assert client.post('/logout').status_code==302


def create(client, **kwargs):
    return client.post('/messages/new',data={'mode':'single','subject':'Ważny temat',
                                              'body':'Proszę o kontakt',**kwargs},content_type='multipart/form-data')


def test_single_and_private_reads(mail_client):
    client,ids=mail_client
    assert client.get('/messages').status_code==302
    login(client,'mail_teacher')
    assert create(client,recipient_id=str(ids['mail_ala'])).status_code==302
    with app.app_context():
        msg=MailMessage.query.one()
        msgid=msg.id
        assert MailRecipient.query.one().read_at is None
    logout(client)
    login(client,'mail_ola')
    assert client.get(f'/messages/{msgid}').status_code==404
    assert client.get(f'/messages/{msgid}/attachment').status_code==404
    assert client.post(f'/messages/{msgid}/move',data={'action':'trash'}).status_code==404
    logout(client)
    login(client,'mail_ala')
    assert 'Ważny temat' in client.get('/messages?folder=unread').get_data(as_text=True)
    assert client.get(f'/messages/{msgid}').status_code==200
    with app.app_context():
        assert MailRecipient.query.one().read_at is not None
    assert 'Ważny temat' not in client.get('/messages?folder=unread').get_data(as_text=True)


def test_group_and_trash_is_personal(mail_client):
    client,ids=mail_client
    login(client,'mail_teacher')
    assert client.post('/messages/new',data={'mode':'group','group':'students',
          'subject':'Wycieczka','body':'Zebranie'}).status_code==302
    with app.app_context():
        assert MailRecipient.query.count()==2
        msgid=MailMessage.query.one().id
    logout(client)
    login(client,'mail_ala')
    assert client.post(f'/messages/{msgid}/move',data={'action':'trash'}).status_code==302
    assert 'Wycieczka' not in client.get('/messages').get_data(as_text=True)
    assert 'Wycieczka' in client.get('/messages?folder=trash').get_data(as_text=True)
    assert client.post(f'/messages/{msgid}/move',data={'action':'restore'}).status_code==302
    assert 'Wycieczka' in client.get('/messages').get_data(as_text=True)
    logout(client)
    login(client,'mail_ola')
    assert 'Wycieczka' in client.get('/messages').get_data(as_text=True)


def test_class_group_only_assigned_students(mail_client):
    client,ids=mail_client
    login(client,'mail_admin')
    assert client.post('/messages/new',data={'mode':'group','group':'class:1A',
           'subject':'Klasa pierwsza','body':'Informacja'}).status_code==302
    with app.app_context():
        assert [r.user_id for r in MailRecipient.query.all()]==[ids['mail_ala']]


def test_safe_attachment(mail_client):
    client,ids=mail_client
    login(client,'mail_teacher')
    uploaded=(BytesIO(b'Witaj uczniu'), 'notatka.txt')
    assert create(client,recipient_id=str(ids['mail_ala']),attachment=uploaded).status_code==302
    with app.app_context():
        msgid=MailMessage.query.one().id
    r=client.get(f'/messages/{msgid}/attachment')
    assert r.status_code==200
    assert r.data==b'Witaj uczniu'
    assert r.headers['X-Content-Type-Options']=='nosniff'
    logout(client)
    login(client,'mail_ola')
    assert client.get(f'/messages/{msgid}/attachment').status_code==404
    logout(client)
    login(client,'mail_ala')
    assert client.get(f'/messages/{msgid}/attachment').data==b'Witaj uczniu'


def test_reject_dangerous_and_oversize_files(mail_client):
    client,ids=mail_client
    login(client,'mail_teacher')
    assert create(client,recipient_id=str(ids['mail_ala']),
                  attachment=(BytesIO(b'print(1)'), 'program.py')).status_code==400
    assert create(client,recipient_id=str(ids['mail_ala']),
                  attachment=(BytesIO(b'a'*262145), 'large.txt')).status_code==413
    assert create(client,recipient_id=str(ids['mail_ala']),
                  attachment=(BytesIO(b'notpdf'), 'bad.pdf')).status_code==400
    with app.app_context():
        assert MailMessage.query.count()==0


def test_group_validation_and_authorization(mail_client):
    client,ids=mail_client
    login(client,'mail_teacher')
    assert client.post('/messages/new',data={'mode':'group','group':'unauthorized',
           'subject':'x','body':'y'}).status_code==400
    assert create(client,recipient_id='99999').status_code==400
    assert create(client,recipient_id=str(ids['mail_ala']),subject='').status_code==200
    with app.app_context():
        assert MailMessage.query.count()==0
