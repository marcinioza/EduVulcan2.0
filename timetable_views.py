"""Plan lekcji: administrator publikuje PDF, pozostali widza swoje klasy."""
from io import BytesIO
from pathlib import Path

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from models import db, Student, TeacherAssignment
from timetable_models import ClassTimetable

MAX_PDF_BYTES = 2 * 1024 * 1024


def allowed_classes():
    if current_user.role == 'admin':
        return sorted({cls for (cls,) in db.session.query(Student.school_class).distinct().all()})
    if current_user.role == 'teacher':
        return sorted({cls for (cls,) in db.session.query(TeacherAssignment.school_class)
                       .filter_by(teacher_id=current_user.id).distinct().all()})
    if current_user.role == 'student':
        if current_user.student_id is None:
            return []
        student = db.session.get(Student, current_user.student_id)
        return [student.school_class] if student is not None else []
    abort(403)


def _pdf_upload(upload):
    if upload is None or not upload.filename:
        abort(400, 'Wybierz plik PDF.')
    filename = secure_filename(upload.filename)
    if not filename or len(filename) > 180 or Path(filename).suffix.lower() != '.pdf':
        abort(400, 'Dozwolone są tylko pliki PDF.')
    raw = upload.stream.read(MAX_PDF_BYTES + 1)
    if not raw or len(raw) > MAX_PDF_BYTES:
        abort(413, 'Plan lekcji musi mieć maksymalnie 2 MB.')
    # Podstawowa kontrola formatu; plik pobierany wyłącznie jako załącznik.
    if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:
        abort(400, 'Plik nie wygląda na poprawny dokument PDF.')
    return filename, raw


def register_timetables(role_bp):
    @role_bp.route('/timetables', methods=['GET', 'POST'])
    @login_required
    def timetables():
        classes = allowed_classes()
        if request.method == 'POST':
            if current_user.role != 'admin':
                abort(403)
            school_class = request.form.get('school_class', '').strip()
            if school_class not in classes:
                abort(400, 'Nieprawidłowa klasa.')
            action = request.form.get('action', '')
            record = ClassTimetable.query.filter_by(school_class=school_class).first()
            if action == 'upload':
                filename, raw = _pdf_upload(request.files.get('file'))
                if record is None:
                    record = ClassTimetable(school_class=school_class, filename=filename,
                                            content=raw, updated_by=current_user.id)
                    db.session.add(record)
                else:
                    record.filename = filename
                    record.content = raw
                    record.updated_by = current_user.id
                db.session.commit()
                flash('Plan lekcji został zapisany.', 'success')
            elif action == 'remove':
                if record is None:
                    abort(404)
                db.session.delete(record)
                db.session.commit()
                flash('Usunięto opublikowany PDF; pusty szablon nadal jest dostępny.', 'success')
            else:
                abort(400)
            return redirect(url_for('roles.timetables', school_class=school_class))

        selected_class = request.args.get('school_class', '').strip()
        if selected_class and selected_class not in classes:
            abort(403)
        if not selected_class and len(classes) == 1:
            selected_class = classes[0]
        records = ClassTimetable.query.filter(ClassTimetable.school_class.in_(classes)).all() if classes else []
        plans = {plan.school_class: plan for plan in records}
        return render_template('timetables.html', classes=classes, selected_class=selected_class,
                               plans=plans, is_admin=current_user.role == 'admin')

    @role_bp.route('/timetables/download/<school_class>')
    @login_required
    def timetable_download(school_class):
        if school_class not in allowed_classes():
            abort(403)
        record = ClassTimetable.query.filter_by(school_class=school_class).first()
        if record is not None:
            response = send_file(BytesIO(record.content), mimetype='application/pdf',
                                 as_attachment=True, download_name=record.filename)
        else:
            template = Path(current_app.root_path) / 'static' / 'files' / 'pusty-plan-lekcji.pdf'
            response = send_file(template, mimetype='application/pdf', as_attachment=True,
                                 download_name=f'plan-lekcji-{secure_filename(school_class)}-szablon.pdf')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'private, no-store'
        return response
