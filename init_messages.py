"""Idempotent, additive migration for school demo messaging tables."""
from app import app
from models import db
from message_models import MailMessage, MailRecipient, MailAttachment

with app.app_context():
    for model in (MailMessage, MailRecipient, MailAttachment):
        model.__table__.create(bind=db.engine, checkfirst=True)
    print('Tabele wiadomości gotowe. Uczniowie, oceny i frekwencja są zachowane.')
