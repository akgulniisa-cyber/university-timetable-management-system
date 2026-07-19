import csv
import io

from flask import Response, flash, redirect, render_template, request, url_for

from extensions import db
from forms import AssignmentForm, DeleteForm, InstructorForm, ModuleForm, ScheduleForm, TrainingForm, SESSION_TYPES
from models import Instructor, Module, ScheduleEntry, TeachingAssignment, Training
from services import (
    assignment_rows,
    build_group_choices,
    build_instructor_choices,
    build_module_choices,
    compute_end_time,
    effective_reference_hours,
    get_training,
    instructor_assigned_hours,
    instructor_scheduled_hours,
    planning_rows,
    scheduled_hours,
    scheduled_hours_excluding,
    instructor_scheduled_hours_excluding,
    validate_assignment_against_module,
)


def register_routes(app):
    def flash_form_errors(form):
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")

    def render_modules_page(form, delete_form, training, editing_module=None):
        modules = Module.query.order_by(Module.module_code.asc()).all()
        return render_template(
            "modules.html",
            form=form,
            modules=modules,
            training=training,
            delete_form=delete_form,
            editing_module=editing_module,
        )

    def render_instructors_page(instructor_form, assignment_form, delete_form, training, editing_instructor=None, editing_assignment=None):
        instructors = Instructor.query.order_by(Instructor.instructor_surname.asc(), Instructor.instructor_name.asc()).all()
        assignments = TeachingAssignment.query.order_by(TeachingAssignment.module_id.asc()).all()
        return render_template(
            "instructors.html",
            instructor_form=instructor_form,
            assignment_form=assignment_form,
            instructors=instructors,
            assignments=assignments,
            assignment_rows=assignment_rows(training),
            delete_form=delete_form,
            editing_instructor=editing_instructor,
            editing_assignment=editing_assignment,
        )

    def render_schedule_page(form, delete_form, training, editing_entry=None):
        entries = ScheduleEntry.query.order_by(ScheduleEntry.date.asc(), ScheduleEntry.start_time.asc()).all()
        return render_template(
            "schedule.html",
            form=form,
            entries=entries,
            planning_rows=planning_rows(training),
            training=training,
            delete_form=delete_form,
            editing_entry=editing_entry,
        )

    @app.route("/")
    def home():
        training = get_training()
        stats = {
            "modules": Module.query.count(),
            "instructors": Instructor.query.count(),
            "assignments": TeachingAssignment.query.count(),
            "sessions": ScheduleEntry.query.count(),
        }
        return render_template("index.html", training=training, stats=stats)

    @app.route("/configure", methods=["GET", "POST"])
    def configure():
        training = get_training()
        form = TrainingForm(obj=training)
        delete_form = DeleteForm()

        if form.validate_on_submit():
            if training is None:
                training = Training()
                db.session.add(training)

            training.training_name = form.training_name.data.strip()
            training.td_groups = form.td_groups.data
            training.tp_groups = form.tp_groups.data
            db.session.commit()
            flash("Configuration de la formation enregistree.", "success")
            return redirect(url_for("configure"))
        if request.method == "POST":
            flash_form_errors(form)

        return render_template("configure.html", form=form, training=training, delete_form=delete_form)

    @app.route("/modules", methods=["GET", "POST"])
    def manage_modules():
        training = get_training()
        form = ModuleForm()
        delete_form = DeleteForm()

        if form.validate_on_submit():
            module = Module.query.filter_by(module_code=form.module_code.data).first()
            if module is None:
                module = Module(module_code=form.module_code.data)
                db.session.add(module)

            module.module_name = form.module_name.data.strip()
            module.cm_hours = form.cm_hours.data
            module.td_hours = form.td_hours.data
            module.tp_hours = form.tp_hours.data
            db.session.commit()
            flash("Module enregistre.", "success")
            return redirect(url_for("manage_modules"))
        if request.method == "POST":
            flash_form_errors(form)

        return render_modules_page(form, delete_form, training)

    @app.route("/modules/<int:module_id>/edit", methods=["GET", "POST"])
    def edit_module(module_id):
        training = get_training()
        module = db.session.get(Module, module_id)
        if module is None:
            flash("Module introuvable.", "danger")
            return redirect(url_for("manage_modules"))

        form = ModuleForm(obj=module)
        delete_form = DeleteForm()

        if form.validate_on_submit():
            module.module_code = form.module_code.data
            module.module_name = form.module_name.data.strip()
            module.cm_hours = form.cm_hours.data
            module.td_hours = form.td_hours.data
            module.tp_hours = form.tp_hours.data
            db.session.commit()
            flash("Module mis a jour.", "success")
            return redirect(url_for("manage_modules"))
        if request.method == "POST":
            flash_form_errors(form)

        return render_modules_page(form, delete_form, training, editing_module=module)

    @app.route("/instructors", methods=["GET", "POST"])
    def manage_instructors():
        training = get_training()
        instructor_form = InstructorForm(prefix="teacher")
        assignment_form = AssignmentForm(prefix="assignment")
        delete_form = DeleteForm()
        assignment_form.module_id.choices = build_module_choices()
        assignment_form.instructor_id.choices = build_instructor_choices()

        if instructor_form.submit.data and instructor_form.validate_on_submit():
            instructor = Instructor(
                instructor_name=instructor_form.instructor_name.data.strip(),
                instructor_surname=instructor_form.instructor_surname.data.strip(),
            )
            db.session.add(instructor)
            db.session.commit()
            flash("Enseignant ajoute.", "success")
            return redirect(url_for("manage_instructors"))
        elif instructor_form.submit.data and request.method == "POST":
            flash_form_errors(instructor_form)

        if assignment_form.submit.data and assignment_form.validate_on_submit():
            assignment = TeachingAssignment.query.filter_by(
                module_id=assignment_form.module_id.data,
                instructor_id=assignment_form.instructor_id.data,
            ).first()
            if assignment is None:
                assignment = TeachingAssignment(
                    module_id=assignment_form.module_id.data,
                    instructor_id=assignment_form.instructor_id.data,
                )
                db.session.add(assignment)

            assignment.cm_hours = assignment_form.cm_hours.data
            assignment.td_hours = assignment_form.td_hours.data
            assignment.tp_hours = assignment_form.tp_hours.data
            is_valid, error_message = validate_assignment_against_module(training, assignment)
            if not is_valid:
                db.session.rollback()
                flash(error_message, "danger")
            else:
                db.session.commit()
                flash("Affectation mise a jour.", "success")
                return redirect(url_for("manage_instructors"))
        elif assignment_form.submit.data and request.method == "POST":
            flash_form_errors(assignment_form)

        return render_instructors_page(instructor_form, assignment_form, delete_form, training)

    @app.route("/instructors/<int:instructor_id>/edit", methods=["GET", "POST"])
    def edit_instructor(instructor_id):
        training = get_training()
        instructor = db.session.get(Instructor, instructor_id)
        if instructor is None:
            flash("Enseignant introuvable.", "danger")
            return redirect(url_for("manage_instructors"))

        instructor_form = InstructorForm(prefix="teacher", obj=instructor)
        assignment_form = AssignmentForm(prefix="assignment")
        assignment_form.module_id.choices = build_module_choices()
        assignment_form.instructor_id.choices = build_instructor_choices()
        delete_form = DeleteForm()

        if instructor_form.validate_on_submit() and instructor_form.submit.data:
            instructor.instructor_name = instructor_form.instructor_name.data.strip()
            instructor.instructor_surname = instructor_form.instructor_surname.data.strip()
            db.session.commit()
            flash("Enseignant mis a jour.", "success")
            return redirect(url_for("manage_instructors"))
        if request.method == "POST" and instructor_form.submit.data:
            flash_form_errors(instructor_form)

        return render_instructors_page(instructor_form, assignment_form, delete_form, training, editing_instructor=instructor)

    @app.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
    def edit_assignment(assignment_id):
        training = get_training()
        assignment = db.session.get(TeachingAssignment, assignment_id)
        if assignment is None:
            flash("Affectation introuvable.", "danger")
            return redirect(url_for("manage_instructors"))

        instructor_form = InstructorForm(prefix="teacher")
        assignment_form = AssignmentForm(prefix="assignment", obj=assignment)
        assignment_form.module_id.choices = build_module_choices()
        assignment_form.instructor_id.choices = build_instructor_choices()
        delete_form = DeleteForm()

        if assignment_form.validate_on_submit() and assignment_form.submit.data:
            assignment.module_id = assignment_form.module_id.data
            assignment.instructor_id = assignment_form.instructor_id.data
            assignment.cm_hours = assignment_form.cm_hours.data
            assignment.td_hours = assignment_form.td_hours.data
            assignment.tp_hours = assignment_form.tp_hours.data
            is_valid, error_message = validate_assignment_against_module(training, assignment)
            if not is_valid:
                db.session.rollback()
                flash(error_message, "danger")
            else:
                db.session.commit()
                flash("Affectation mise a jour.", "success")
                return redirect(url_for("manage_instructors"))
        if request.method == "POST" and assignment_form.submit.data:
            flash_form_errors(assignment_form)

        return render_instructors_page(
            instructor_form,
            assignment_form,
            delete_form,
            training,
            editing_assignment=assignment,
        )

    @app.route("/schedule", methods=["GET", "POST"])
    def manage_schedule():
        training = get_training()
        form = ScheduleForm(prefix="schedule")
        delete_form = DeleteForm()
        form.module_id.choices = build_module_choices()
        form.instructor_id.choices = build_instructor_choices()

        selected_session_type = form.session_type.data or "CM"
        if selected_session_type not in SESSION_TYPES:
            selected_session_type = "CM"
        form.group_code.choices = build_group_choices(training, selected_session_type)

        if form.submit.data and form.validate_on_submit():
            module = db.session.get(Module, form.module_id.data)
            instructor = db.session.get(Instructor, form.instructor_id.data)
            quota = effective_reference_hours(module, training, form.session_type.data)
            already_placed = scheduled_hours(module.id, form.session_type.data)
            assigned_total = instructor_assigned_hours(module.id, instructor.id, form.session_type.data)
            already_planned_for_instructor = instructor_scheduled_hours(module.id, instructor.id, form.session_type.data)

            if already_placed + form.duration.data > quota + 0.01:
                flash(
                    f"Quota depasse pour {module.module_code} en {form.session_type.data}: {already_placed:.1f}h deja placees sur {quota:.1f}h.",
                    "danger",
                )
            elif assigned_total <= 0:
                flash("Cet enseignant n'a aucune heure affectee sur ce module et ce type de seance.", "danger")
            elif already_planned_for_instructor + form.duration.data > assigned_total + 0.01:
                flash(
                    f"L'enseignant depasse son volume affecte ({assigned_total:.1f}h) pour cette seance.",
                    "danger",
                )
            else:
                entry = ScheduleEntry(
                    module_id=module.id,
                    instructor_id=instructor.id,
                    session_type=form.session_type.data,
                    group_code=form.group_code.data,
                    date=form.date.data,
                    start_time=form.start_time.data,
                    end_time=compute_end_time(form.start_time.data, form.duration.data),
                    duration=form.duration.data,
                )
                db.session.add(entry)
                db.session.commit()
                flash("Seance planifiee.", "success")
                return redirect(url_for("manage_schedule"))
        elif form.submit.data and request.method == "POST":
            flash_form_errors(form)

        return render_schedule_page(form, delete_form, training)

    @app.route("/schedule/<int:entry_id>/edit", methods=["GET", "POST"])
    def edit_schedule_entry(entry_id):
        training = get_training()
        entry = db.session.get(ScheduleEntry, entry_id)
        if entry is None:
            flash("Seance introuvable.", "danger")
            return redirect(url_for("manage_schedule"))

        form = ScheduleForm(prefix="schedule", obj=entry)
        delete_form = DeleteForm()
        form.module_id.choices = build_module_choices()
        form.instructor_id.choices = build_instructor_choices()
        selected_session_type = form.session_type.data or entry.session_type or "CM"
        if selected_session_type not in SESSION_TYPES:
            selected_session_type = "CM"
        form.group_code.choices = build_group_choices(training, selected_session_type)

        if form.validate_on_submit() and form.submit.data:
            module = db.session.get(Module, form.module_id.data)
            instructor = db.session.get(Instructor, form.instructor_id.data)
            quota = effective_reference_hours(module, training, form.session_type.data)
            already_placed = scheduled_hours_excluding(module.id, form.session_type.data, entry.id)
            assigned_total = instructor_assigned_hours(module.id, instructor.id, form.session_type.data)
            already_planned_for_instructor = instructor_scheduled_hours_excluding(
                module.id,
                instructor.id,
                form.session_type.data,
                entry.id,
            )

            if already_placed + form.duration.data > quota + 0.01:
                flash(
                    f"Quota depasse pour {module.module_code} en {form.session_type.data}: {already_placed:.1f}h deja placees sur {quota:.1f}h.",
                    "danger",
                )
            elif assigned_total <= 0:
                flash("Cet enseignant n'a aucune heure affectee sur ce module et ce type de seance.", "danger")
            elif already_planned_for_instructor + form.duration.data > assigned_total + 0.01:
                flash(
                    f"L'enseignant depasse son volume affecte ({assigned_total:.1f}h) pour cette seance.",
                    "danger",
                )
            else:
                entry.module_id = module.id
                entry.instructor_id = instructor.id
                entry.session_type = form.session_type.data
                entry.group_code = form.group_code.data
                entry.date = form.date.data
                entry.start_time = form.start_time.data
                entry.end_time = compute_end_time(form.start_time.data, form.duration.data)
                entry.duration = form.duration.data
                db.session.commit()
                flash("Seance mise a jour.", "success")
                return redirect(url_for("manage_schedule"))
        if request.method == "POST" and form.submit.data:
            flash_form_errors(form)

        return render_schedule_page(form, delete_form, training, editing_entry=entry)

    @app.route("/modules/<int:module_id>/delete", methods=["POST"])
    def delete_module(module_id):
        form = DeleteForm()
        if form.validate_on_submit():
            module = db.session.get(Module, module_id)
            if module is not None:
                db.session.delete(module)
                db.session.commit()
                flash("Module supprime.", "success")
        return redirect(url_for("manage_modules"))

    @app.route("/instructors/<int:instructor_id>/delete", methods=["POST"])
    def delete_instructor(instructor_id):
        form = DeleteForm()
        if form.validate_on_submit():
            instructor = db.session.get(Instructor, instructor_id)
            if instructor is not None:
                db.session.delete(instructor)
                db.session.commit()
                flash("Enseignant supprime.", "success")
        return redirect(url_for("manage_instructors"))

    @app.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
    def delete_assignment(assignment_id):
        form = DeleteForm()
        if form.validate_on_submit():
            assignment = db.session.get(TeachingAssignment, assignment_id)
            if assignment is not None:
                db.session.delete(assignment)
                db.session.commit()
                flash("Affectation supprimee.", "success")
        return redirect(url_for("manage_instructors"))

    @app.route("/schedule/<int:entry_id>/delete", methods=["POST"])
    def delete_schedule_entry(entry_id):
        form = DeleteForm()
        if form.validate_on_submit():
            entry = db.session.get(ScheduleEntry, entry_id)
            if entry is not None:
                db.session.delete(entry)
                db.session.commit()
                flash("Seance supprimee.", "success")
        return redirect(url_for("manage_schedule"))

    @app.route("/schedule/export")
    def export_schedule():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Module", "Instructor", "Type", "Group", "Start", "End", "Duration"])

        entries = ScheduleEntry.query.order_by(ScheduleEntry.date.asc(), ScheduleEntry.start_time.asc()).all()
        for entry in entries:
            writer.writerow(
                [
                    entry.date.strftime("%Y-%m-%d"),
                    entry.module.module_code,
                    entry.instructor.full_name,
                    entry.session_type,
                    entry.group_code,
                    entry.start_time.strftime("%H:%M"),
                    entry.end_time.strftime("%H:%M"),
                    entry.duration,
                ]
            )

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=schedule_export.csv"},
        )