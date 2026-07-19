from extensions import db


class Training(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    training_name = db.Column(db.String(100), nullable=False)
    td_groups = db.Column(db.Integer, nullable=False, default=1)
    tp_groups = db.Column(db.Integer, nullable=False, default=1)

    def group_multiplier(self, session_type):
        if session_type == "TD":
            return max(self.td_groups, 1)
        if session_type == "TP":
            return max(self.tp_groups, 1)
        return 1


class Module(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    module_code = db.Column(db.String(50), nullable=False, unique=True)
    module_name = db.Column(db.String(100), nullable=False)
    cm_hours = db.Column(db.Integer, nullable=False, default=0)
    td_hours = db.Column(db.Integer, nullable=False, default=0)
    tp_hours = db.Column(db.Integer, nullable=False, default=0)

    def reference_hours(self, session_type):
        if session_type == "CM":
            return self.cm_hours
        if session_type == "TD":
            return self.td_hours
        return self.tp_hours


class Instructor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instructor_name = db.Column(db.String(100), nullable=False)
    instructor_surname = db.Column(db.String(100), nullable=False)

    @property
    def full_name(self):
        return f"{self.instructor_name} {self.instructor_surname}"


class TeachingAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("module.id"), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("instructor.id"), nullable=False)
    cm_hours = db.Column(db.Float, nullable=False, default=0)
    td_hours = db.Column(db.Float, nullable=False, default=0)
    tp_hours = db.Column(db.Float, nullable=False, default=0)

    module = db.relationship("Module", backref=db.backref("assignments", lazy=True, cascade="all, delete-orphan"))
    instructor = db.relationship("Instructor", backref=db.backref("assignments", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("module_id", "instructor_id", name="uq_assignment_module_instructor"),)

    def hours_for(self, session_type):
        if session_type == "CM":
            return self.cm_hours
        if session_type == "TD":
            return self.td_hours
        return self.tp_hours


class ScheduleEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("module.id"), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey("instructor.id"), nullable=False)
    session_type = db.Column(db.String(10), nullable=False)
    group_code = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Float, nullable=False)

    module = db.relationship("Module", backref=db.backref("schedule_entries", lazy=True, cascade="all, delete-orphan"))
    instructor = db.relationship("Instructor", backref=db.backref("schedule_entries", lazy=True, cascade="all, delete-orphan"))