"""Private mailbox models: independent per-recipient read/trash states."""
from datetime import datetime, timezone
from models import db


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MailMessage(db.Model):
    __tablename__ = 'mail_messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subject = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    sender_deleted = db.Column(db.Boolean, nullable=False, default=False)
    sender = db.relationship('User', foreign_keys=[sender_id])
    recipients = db.relationship('MailRecipient', back_populates='message', cascade='all, delete-orphan')
    attachment = db.relationship('MailAttachment', back_populates='message', uselist=False, cascade='all, delete-orphan')


class MailRecipient(db.Model):
    __tablename__ = 'mail_recipients'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('mail_messages.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    trashed_at = db.Column(db.DateTime, nullable=True)
    message = db.relationship('MailMessage', back_populates='recipients')
    user = db.relationship('User')
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='uq_mail_delivery'),)


class MailAttachment(db.Model):
    __tablename__ = 'mail_attachments'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('mail_messages.id'), unique=True, nullable=False)
    filename = db.Column(db.String(180), nullable=False)
    mime_type = db.Column(db.String(80), nullable=False)
    content = db.Column(db.LargeBinary(length=262144), nullable=False)
    message = db.relationship('MailMessage', back_populates='attachment')
