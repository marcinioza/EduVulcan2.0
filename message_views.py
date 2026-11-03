"""School demo messages: inbox, sent, unread, trash and private attachments."""
from io import BytesIO
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from models import db, Student, User
from message_models import MailAttachment, MailMessage, MailRecipient, utc_now

MAX_FILE_BYTES = 256 * 1024
ACCEPTED_FILES = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.txt': 'text/plain',
}
GROUP_LABELS = {
    'all': 'Wszyscy użytkownicy',
    'students': 'Wszyscy uczniowie',
    'teachers': 'Wszyscy nauczyciele',
    'admins': 'Administratorzy',
}


def _recipient_or_404(message_id):
    delivery = MailRecipient.query.filter_by(message_id=message_id, user_id=current_user.id).first()
    if delivery is None:
        abort(404)
    return delivery


def _can_open(message):
    if message.sender_id == current_user.id and not message.sender_deleted:
        return True
    return MailRecipient.query.filter_by(message_id=message.id, user_id=current_user.id).first() is not None


def _members(group):
    if group == 'all':
        return User.query.all()
    if group in ('students', 'teachers', 'admins'):
        role = {'students': 'student', 'teachers': 'teacher', 'admins': 'admin'}[group]
        return User.query.filter_by(role=role).all()
    if group.startswith('class:'):
        school_class = group.removeprefix('class:')
        if not school_class or len(school_class) > 30:
            abort(400)
        # The class is based on a student account's linked school class.
        return User.query.join(Student, User.student_id == Student.id).filter(
            User.role == 'student', Student.school_class == school_class
        ).all()
    abort(400)


def _attachment_data(upload):
    if upload is None or not upload.filename:
        return None
    filename = secure_filename(upload.filename)
    if not filename or len(filename) > 180:
        abort(400, 'Niepoprawna nazwa załącznika.')
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPTED_FILES:
        abort(400, 'Załącznik: dozwolone PDF, PNG, JPG oraz TXT.')
    raw = upload.stream.read(MAX_FILE_BYTES + 1)
    if not raw or len(raw) > MAX_FILE_BYTES:
        abort(413, 'Załącznik musi mieć od 1 bajta do 256 KB.')
    # Extension plus signature validation (MIME supplied by the client is untrusted).
    if ext == '.pdf' and not raw.startswith(b'%PDF-'):
        abort(400, 'Niepoprawny plik PDF.')
    if ext == '.png' and not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        abort(400, 'Niepoprawny plik PNG.')
    if ext in ('.jpg', '.jpeg') and not raw.startswith(b'\xff\xd8\xff'):
        abort(400, 'Niepoprawny plik JPG.')
    if ext == '.txt':
        try:
            raw.decode('utf-8')
        except UnicodeDecodeError:
            abort(400, 'Plik TXT musi być w UTF-8.')
    return filename, ACCEPTED_FILES[ext], raw


def register_messages(role_bp):
    @role_bp.route('/messages')
    @login_required
    def mailbox():
        folder = request.args.get('folder', 'inbox')
        if folder not in {'inbox', 'unread', 'sent', 'trash'}:
            abort(404)
        if folder == 'sent':
            records = (MailMessage.query.filter_by(sender_id=current_user.id, sender_deleted=False)
                       .order_by(MailMessage.created_at.desc(), MailMessage.id.desc()).limit(200).all())
        else:
            query = MailRecipient.query.join(MailMessage).filter(MailRecipient.user_id == current_user.id)
            if folder == 'trash':
                query = query.filter(MailRecipient.trashed_at.isnot(None))
            else:
                query = query.filter(MailRecipient.trashed_at.is_(None))
            if folder == 'unread':
                query = query.filter(MailRecipient.read_at.is_(None))
            records = query.order_by(MailMessage.created_at.desc(), MailMessage.id.desc()).limit(200).all()
        unread = MailRecipient.query.filter_by(user_id=current_user.id, read_at=None, trashed_at=None).count()
        return render_template('mailbox.html', folder=folder, records=records, unread=unread)

    @role_bp.route('/messages/new', methods=['GET', 'POST'])
    @login_required
    def message_new():
        users = User.query.filter(User.id != current_user.id).order_by(User.role, User.username).all()
        classes = [name for (name,) in db.session.query(Student.school_class).distinct().order_by(Student.school_class).all()]
        if request.method == 'POST':
            mode = request.form.get('mode', '')
            subject = request.form.get('subject', '').strip()
            body = request.form.get('body', '').strip()
            if not 1 <= len(subject) <= 150 or not 1 <= len(body) <= 10000:
                flash('Temat (1–150 znaków) i treść (1–10000 znaków) są wymagane.', 'error')
                return render_template('message_new.html', users=users, classes=classes)
            if mode == 'single':
                raw_id = request.form.get('recipient_id', '')
                recipient = db.session.get(User, int(raw_id)) if raw_id.isdigit() else None
                if recipient is None:
                    abort(400)
                recipients = [recipient]
            elif mode == 'group':
                recipients = _members(request.form.get('group', ''))
            else:
                abort(400)
            recipients = sorted({user.id: user for user in recipients if user.id != current_user.id}.values(), key=lambda u: u.id)
            if not recipients:
                flash('Brak odbiorców. Wybierz inną osobę lub grupę.', 'error')
                return render_template('message_new.html', users=users, classes=classes)
            if len(recipients) > 200:
                abort(400, 'Wiadomość grupowa: limit 200 odbiorców.')
            attachment = _attachment_data(request.files.get('attachment'))
            message = MailMessage(sender_id=current_user.id, subject=subject, body=body)
            db.session.add(message)
            db.session.flush()
            db.session.add_all([MailRecipient(message_id=message.id, user_id=user.id) for user in recipients])
            if attachment:
                filename, mime_type, content = attachment
                db.session.add(MailAttachment(message_id=message.id, filename=filename,
                                              mime_type=mime_type, content=content))
            db.session.commit()
            flash(f'Wysłano wiadomość do {len(recipients)} odbiorców.', 'success')
            return redirect(url_for('roles.mailbox', folder='sent'))
        return render_template('message_new.html', users=users, classes=classes)

    @role_bp.route('/messages/<int:message_id>')
    @login_required
    def message_read(message_id):
        message = db.get_or_404(MailMessage, message_id)
        delivery = MailRecipient.query.filter_by(message_id=message.id, user_id=current_user.id).first()
        if delivery is None and (message.sender_id != current_user.id or message.sender_deleted):
            abort(404)
        if delivery is not None and delivery.trashed_at is None and delivery.read_at is None:
            delivery.read_at = utc_now()
            db.session.commit()
        return render_template('message_read.html', item=message, delivery=delivery)

    @role_bp.route('/messages/<int:message_id>/attachment')
    @login_required
    def message_attachment(message_id):
        message = db.get_or_404(MailMessage, message_id)
        if not _can_open(message):
            abort(404)
        file = message.attachment
        if file is None:
            abort(404)
        response = send_file(BytesIO(file.content), mimetype=file.mime_type,
                             as_attachment=True, download_name=file.filename)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @role_bp.route('/messages/<int:message_id>/move', methods=['POST'])
    @login_required
    def message_move(message_id):
        action = request.form.get('action', '')
        message = db.get_or_404(MailMessage, message_id)
        delivery = MailRecipient.query.filter_by(message_id=message.id, user_id=current_user.id).first()
        if action == 'trash':
            if delivery:
                delivery.trashed_at = utc_now()
            elif message.sender_id == current_user.id and not message.sender_deleted:
                message.sender_deleted = True
            else:
                abort(404)
        elif action == 'restore':
            if delivery is None or delivery.trashed_at is None:
                abort(404)
            delivery.trashed_at = None
        elif action == 'unread':
            if delivery is None or delivery.trashed_at is not None:
                abort(404)
            delivery.read_at = None
        else:
            abort(400)
        db.session.commit()
        return redirect(url_for('roles.mailbox', folder='trash' if action == 'trash' else 'inbox'))
