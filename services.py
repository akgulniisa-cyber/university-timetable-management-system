import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import current_app

from extensions import db
from forms import SESSION_TYPES
from models import Instructor, Module, ScheduleEntry, TeachingAssignment, Training


def get_training():
    return Training.query.order_by(Training.id.asc()).first()


def build_module_choices():
    return [(0, "Choisir un module")] + [
        (module.id, f"{module.module_code} - {module.module_name}")
        for module in Module.query.order_by(Module.module_code.asc()).all()
    ]


def build_instructor_choices():
    return [(0, "Choisir un enseignant")] + [
        (instructor.id, instructor.full_name)
        for instructor in Instructor.query.order_by(Instructor.instructor_surname.asc(), Instructor.instructor_name.asc()).all()
    ]


def build_group_choices(training, session_type):
    if session_type == "CM":
        return [("PROMO", "Promotion complete")]
    if session_type == "TD":
        count = training.td_groups if training else 1
        return [(f"TD{index}", f"Groupe TD {index}") for index in range(1, count + 1)]
    count = training.tp_groups if training else 1
    return [(f"TP{index}", f"Groupe TP {index}") for index in range(1, count + 1)]


def effective_reference_hours(module, training, session_type):
    if module is None:
        return 0
    multiplier = training.group_multiplier(session_type) if training else 1
    return float(module.reference_hours(session_type) * multiplier)


def assigned_hours(module_id, session_type):
    assignments = TeachingAssignment.query.filter_by(module_id=module_id).all()
    return round(sum(assignment.hours_for(session_type) for assignment in assignments), 2)


def assigned_hours_excluding(module_id, session_type, assignment_id):
    assignments = TeachingAssignment.query.filter_by(module_id=module_id).all()
    return round(sum(assignment.hours_for(session_type) for assignment in assignments if assignment.id != assignment_id), 2)


def instructor_assigned_hours(module_id, instructor_id, session_type):
    assignment = TeachingAssignment.query.filter_by(module_id=module_id, instructor_id=instructor_id).first()
    if assignment is None:
        return 0.0
    return round(assignment.hours_for(session_type), 2)


def scheduled_hours(module_id, session_type):
    entries = ScheduleEntry.query.filter_by(module_id=module_id, session_type=session_type).all()
    return round(sum(entry.duration for entry in entries), 2)


def scheduled_hours_excluding(module_id, session_type, entry_id):
    entries = ScheduleEntry.query.filter_by(module_id=module_id, session_type=session_type).all()
    return round(sum(entry.duration for entry in entries if entry.id != entry_id), 2)


def instructor_scheduled_hours(module_id, instructor_id, session_type):
    entries = ScheduleEntry.query.filter_by(
        module_id=module_id,
        instructor_id=instructor_id,
        session_type=session_type,
    ).all()
    return round(sum(entry.duration for entry in entries), 2)


def instructor_scheduled_hours_excluding(module_id, instructor_id, session_type, entry_id):
    entries = ScheduleEntry.query.filter_by(
        module_id=module_id,
        instructor_id=instructor_id,
        session_type=session_type,
    ).all()
    return round(sum(entry.duration for entry in entries if entry.id != entry_id), 2)


def compute_end_time(start_time, duration):
    start_datetime = datetime.combine(date.today(), start_time)
    end_datetime = start_datetime + timedelta(hours=float(duration))
    return end_datetime.time().replace(second=0, microsecond=0)


def assignment_rows(training):
    rows = []
    for module in Module.query.order_by(Module.module_code.asc()).all():
        expected = {session_type: effective_reference_hours(module, training, session_type) for session_type in SESSION_TYPES}
        allocated = {session_type: assigned_hours(module.id, session_type) for session_type in SESSION_TYPES}
        rows.append(
            {
                "module": module,
                "expected": expected,
                "allocated": allocated,
                "balanced": all(abs(expected[key] - allocated[key]) < 0.01 for key in SESSION_TYPES),
            }
        )
    return rows


def planning_rows(training):
    rows = []
    for module in Module.query.order_by(Module.module_code.asc()).all():
        quotas = {session_type: effective_reference_hours(module, training, session_type) for session_type in SESSION_TYPES}
        placed = {session_type: scheduled_hours(module.id, session_type) for session_type in SESSION_TYPES}
        rows.append(
            {
                "module": module,
                "quotas": quotas,
                "placed": placed,
                "complete": all(placed[key] <= quotas[key] + 0.01 for key in SESSION_TYPES),
            }
        )
    return rows


def validate_assignment_against_module(training, assignment):
    module = db.session.get(Module, assignment.module_id)
    checks = {
        "CM": assignment.cm_hours,
        "TD": assignment.td_hours,
        "TP": assignment.tp_hours,
    }

    for session_type, new_hours in checks.items():
        quota = effective_reference_hours(module, training, session_type)
        current = assigned_hours_excluding(module.id, session_type, assignment.id)
        if current + new_hours > quota + 0.01:
            return (
                False,
                f"Affectation invalide pour {module.module_code} en {session_type}: {current:.1f}h deja distribuees pour un quota de {quota:.1f}h.",
            )

    return True, None


def initialize_legacy_safe_schema():
    database_path = os.path.join(current_app.instance_path, "project.db")
    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS teaching_assignment ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "module_id INTEGER NOT NULL, "
            "instructor_id INTEGER NOT NULL, "
            "cm_hours FLOAT NOT NULL DEFAULT 0, "
            "td_hours FLOAT NOT NULL DEFAULT 0, "
            "tp_hours FLOAT NOT NULL DEFAULT 0, "
            "UNIQUE(module_id, instructor_id))"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS schedule_entry ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "module_id INTEGER NOT NULL, "
            "instructor_id INTEGER NOT NULL, "
            "session_type VARCHAR(10) NOT NULL, "
            "group_code VARCHAR(20) NOT NULL DEFAULT 'PROMO', "
            "date DATE NOT NULL, "
            "start_time TIME NOT NULL, "
            "end_time TIME NOT NULL DEFAULT '00:00', "
            "duration FLOAT NOT NULL)"
        )
        connection.commit()
    finally:
        connection.close()


def initialize_database():
    initialize_legacy_safe_schema()
    db.create_all()