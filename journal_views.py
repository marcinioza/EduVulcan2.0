"""Dziennik klasowy: wybór klasy, oceny opisowe, edycja, usuwanie."""
from collections import defaultdict
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import and_, or_
from models import db, Grade, Student, Subject, TeacherAssignment
from grade_metadata import GradeMetadata, GRADE_KINDS


def register_journal(role_bp, role_required):
    @role_bp.route('/teacher/journal', methods=['GET', 'POST'])
    @role_required('teacher')
    def teacher_journal():
        assignments = TeacherAssignment.query.filter_by(teacher_id=current_user.id).all()
        allowed_pairs = {(a.school_class, a.subject_id) for a in assignments}
        classes = sorted({a.school_class for a in assignments})
        selected_class = request.args.get('class', '').strip()
        if selected_class and selected_class not in classes:
            abort(403)

        if request.method == 'POST':
            action = request.form.get('action', '')
            school_class = request.form.get('school_class', '').strip()
            if school_class not in classes:
                abort(403)

            if action == 'create':
                student_id = request.form.get('student_id', '')
                subject_id = request.form.get('subject_id', '')
                value = request.form.get('value', '')
                kind = request.form.get('kind', '')
                description = request.form.get('description', '').strip()
                student = db.session.get(Student, int(student_id)) if student_id.isdigit() else None
                subject = db.session.get(Subject, int(subject_id)) if subject_id.isdigit() else None
                if not student or not subject or student.school_class != school_class:
                    abort(400)
                if (student.school_class, subject.id) not in allowed_pairs:
                    abort(403)
                if value not in {'1', '2', '3', '4', '5', '6'} or kind not in GRADE_KINDS or len(description) > 120:
                    abort(400)
                grade = Grade(student_id=student.id, subject_id=subject.id, value=int(value))
                db.session.add(grade)
                db.session.flush()
                db.session.add(GradeMetadata(grade_id=grade.id, kind=kind, description=description))
                db.session.commit()
                flash('Ocena zapisana.', 'success')

            elif action in {'update', 'delete'}:
                grade_id = request.form.get('grade_id', '')
                grade = db.session.get(Grade, int(grade_id)) if grade_id.isdigit() else None
                if grade is None:
                    abort(404)
                if grade.student.school_class != school_class:
                    abort(403)
                if (grade.student.school_class, grade.subject_id) not in allowed_pairs:
                    abort(403)
                if action == 'delete':
                    meta = db.session.get(GradeMetadata, grade.id)
                    if meta:
                        db.session.delete(meta)
                    db.session.delete(grade)
                    db.session.commit()
                    flash('Ocena usunięta.', 'success')
                else:
                    value = request.form.get('value', '')
                    kind = request.form.get('kind', '')
                    description = request.form.get('description', '').strip()
                    if value not in {'1', '2', '3', '4', '5', '6'} or kind not in GRADE_KINDS or len(description) > 120:
                        abort(400)
                    grade.value = int(value)
                    meta = db.session.get(GradeMetadata, grade.id)
                    if meta is None:
                        meta = GradeMetadata(grade_id=grade.id)
                        db.session.add(meta)
                    meta.kind = kind
                    meta.description = description
                    db.session.commit()
                    flash('Ocena zmieniona.', 'success')
            else:
                abort(400)
            return redirect(url_for('roles.teacher_journal', **{'class': school_class}))

        students = []
        subjects = []
        grouped = defaultdict(list)
        if selected_class:
            students = Student.query.filter_by(school_class=selected_class).order_by(Student.last_name, Student.first_name).all()
            subject_ids = {sid for cls, sid in allowed_pairs if cls == selected_class}
            subjects = Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all() if subject_ids else []
            if students and subject_ids:
                student_ids = [student.id for student in students]
                grades = Grade.query.filter(Grade.student_id.in_(student_ids), Grade.subject_id.in_(subject_ids)).order_by(Grade.created_at.desc(), Grade.id.desc()).all()
                meta_by_id = {m.grade_id: m for m in GradeMetadata.query.filter(GradeMetadata.grade_id.in_([g.id for g in grades])).all()} if grades else {}
                for grade in grades:
                    meta = meta_by_id.get(grade.id)
                    kind = meta.kind if meta and meta.kind in GRADE_KINDS else 'inne'
                    grouped[grade.student_id].append({
                        'grade': grade, 'kind': kind, 'kind_label': GRADE_KINDS[kind][0],
                        'color': GRADE_KINDS[kind][1], 'description': meta.description if meta else '',
                    })
        return render_template('teacher_journal.html', classes=classes, selected_class=selected_class,
                               students=students, subjects=subjects, grouped=grouped, kinds=GRADE_KINDS)

    @role_bp.route('/student/grades')
    @role_required('student')
    def student_detailed_grades():
        if current_user.student_id is None:
            abort(403)
        student = db.session.get(Student, current_user.student_id)
        if student is None:
            abort(403)
        grades = Grade.query.filter_by(student_id=student.id).order_by(Grade.created_at.desc(), Grade.id.desc()).all()
        metadata = {m.grade_id: m for m in GradeMetadata.query.filter(GradeMetadata.grade_id.in_([g.id for g in grades])).all()} if grades else {}
        items = []
        for grade in grades:
            meta = metadata.get(grade.id)
            kind = meta.kind if meta and meta.kind in GRADE_KINDS else 'inne'
            items.append({'grade': grade, 'label': GRADE_KINDS[kind][0],
                          'color': GRADE_KINDS[kind][1], 'description': meta.description if meta else ''})
        return render_template('student_detailed_grades.html', student=student, items=items)
