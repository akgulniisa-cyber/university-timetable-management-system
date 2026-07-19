from datetime import date

from flask_wtf import FlaskForm
from wtforms import FloatField, HiddenField, IntegerField, SelectField, StringField, SubmitField
from wtforms.fields import DateField, TimeField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, ValidationError


SESSION_TYPES = ("CM", "TD", "TP")


class TrainingForm(FlaskForm):
    training_name = StringField("Nom de la formation", validators=[DataRequired(), Length(max=100)])
    td_groups = IntegerField("Nombre de groupes TD", validators=[InputRequired(), NumberRange(min=1, max=20)])
    tp_groups = IntegerField("Nombre de groupes TP", validators=[InputRequired(), NumberRange(min=1, max=20)])
    submit = SubmitField("Enregistrer")


class ModuleForm(FlaskForm):
    module_code = StringField("Code du module", validators=[DataRequired(), Length(max=50)])
    module_name = StringField("Libelle du module", validators=[DataRequired(), Length(max=100)])
    cm_hours = IntegerField("Heures CM", validators=[InputRequired(), NumberRange(min=0, max=500)])
    td_hours = IntegerField("Heures TD", validators=[InputRequired(), NumberRange(min=0, max=500)])
    tp_hours = IntegerField("Heures TP", validators=[InputRequired(), NumberRange(min=0, max=500)])
    submit = SubmitField("Enregistrer")

    def validate_module_code(self, field):
        field.data = field.data.strip().upper()


class InstructorForm(FlaskForm):
    instructor_name = StringField("Nom", validators=[DataRequired(), Length(max=100)])
    instructor_surname = StringField("Prenom", validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Ajouter")


class DeleteForm(FlaskForm):
    target_id = HiddenField()
    submit = SubmitField("Supprimer")


class AssignmentForm(FlaskForm):
    module_id = SelectField("Module", coerce=int, validators=[NumberRange(min=1, message="Choisissez un module.")])
    instructor_id = SelectField("Enseignant", coerce=int, validators=[NumberRange(min=1, message="Choisissez un enseignant.")])
    cm_hours = FloatField("Heures CM affectees", validators=[InputRequired(), NumberRange(min=0, max=500)])
    td_hours = FloatField("Heures TD affectees", validators=[InputRequired(), NumberRange(min=0, max=500)])
    tp_hours = FloatField("Heures TP affectees", validators=[InputRequired(), NumberRange(min=0, max=500)])
    submit = SubmitField("Mettre a jour")


class ScheduleForm(FlaskForm):
    module_id = SelectField("Module", coerce=int, validators=[NumberRange(min=1, message="Choisissez un module.")])
    instructor_id = SelectField("Enseignant", coerce=int, validators=[NumberRange(min=1, message="Choisissez un enseignant.")])
    session_type = SelectField(
        "Type de seance",
        choices=[(session_type, session_type) for session_type in SESSION_TYPES],
        validators=[DataRequired()],
    )
    group_code = SelectField("Groupe", validators=[DataRequired()])
    date = DateField("Date", validators=[InputRequired()], default=date.today)
    start_time = TimeField("Heure de debut", validators=[InputRequired()])
    duration = FloatField("Duree (heures)", validators=[InputRequired(), NumberRange(min=0.5, max=12)])
    submit = SubmitField("Planifier")

    def validate_group_code(self, field):
        valid_values = {choice[0] for choice in self.group_code.choices}
        if field.data not in valid_values:
            raise ValidationError("Choisissez un groupe valide.")