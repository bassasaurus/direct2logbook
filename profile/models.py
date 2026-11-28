from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date
from .reminder_integrity import reminder_conditions


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/{1}'.format(instance.user.id, filename)


class Profile(models.Model):
    class DistanceUnit(models.TextChoices):
        NM = 'nm', 'NM'
        MI = 'mi', 'mi'
        KM = 'km', 'km'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    distance_unit = models.CharField(max_length=2, choices=DistanceUnit.choices, default=DistanceUnit.NM)
    company = models.CharField(max_length=50, default='', blank=True)
    student_pilot_certificate = models.BooleanField(default=False)
    sport_pilot_certificate = models.BooleanField(default=False)
    recreational_pilot_certificate = models.BooleanField(default=False)
    private_pilot_certificate = models.BooleanField(default=False)
    commercial_pilot_certificate = models.BooleanField(default=False)
    atp_certificate = models.BooleanField(default=False)
    flight_instructor_certificate = models.BooleanField(default=False)
    instrument_instructor = models.BooleanField(default=False)
    multi_engine_instructor = models.BooleanField(default=False)

    medical_issue_date = models.DateField(default=date.today)
    first_class = models.BooleanField(default=False)
    second_class = models.BooleanField(default=False)
    third_class = models.BooleanField(default=False)
    over_40 = models.BooleanField(default=False)
    web_reminder_preferences = models.JSONField(default=dict, blank=True, editable=False)
    medical_warning_dismissed_for = models.DateField(null=True, blank=True, editable=False)

    free_access = models.BooleanField(default=False)
    # stripe api response fields
    customer_id = models.CharField(max_length=50, blank=True)
    subscription_id = models.CharField(max_length=50, blank=True)
    active = models.BooleanField(default=False)
    expired = models.BooleanField(default=False)
    monthly = models.BooleanField(default=False)
    yearly = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)
    trial = models.BooleanField(default=False)
    trial_expiring = models.BooleanField(default=False)
    today = timezone.now()
    end_date = models.DateField(default=None, null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(flight_instructor_certificate=True) | models.Q(instrument_instructor=False, multi_engine_instructor=False),
            name='profile_instructor_ratings_require_cfi',
        )]

    def __str__(self):
        title = "{} {}".format(self.user, self.pk)
        return title


class Reminder(models.Model):
    class Kind(models.TextChoices):
        EXPIRATION = 'expiration', 'Expiration date'
        FLIGHT_REVIEW = 'flight_review', 'Flight Review'
        INSTRUCTOR_RENEWAL = 'instructor_renewal', 'Flight Instructor Renewal'
        IPC = 'ipc', 'Instrument Currency Review (IPC)'
        FLIGHT_TIME = 'flight_time', 'Total flight time'
        TIME_IN_TYPE = 'time_in_type', 'Time in Type'
        CREW_IN_TYPE = 'crew_in_type', 'Crew Position in Type'
        COMPANY_TIME = 'company_time', 'Time at Company'
        FLIGHT_CONDITION = 'flight_condition', 'Flight Conditions'

    class CompletionType(models.TextChoices):
        FLIGHT_REVIEW = 'flight_review', 'Flight Review'
        PROFICIENCY_CHECK = 'proficiency_check', 'Qualifying Pilot Proficiency Check'
        PRACTICAL_TEST = 'practical_test', 'Pilot Practical Test'
        CFI_PRACTICAL_TEST = 'cfi_practical_test', 'Flight Instructor Practical Test'
        WINGS = 'wings', 'Completed WINGS Phase'

    class CrewPosition(models.TextChoices):
        PIC = 'pilot_in_command', 'PIC'
        SIC = 'second_in_command', 'SIC'
        SOLO = 'solo', 'Solo'
        DUAL = 'dual', 'Dual'

    class FlightCondition(models.TextChoices):
        PIC = 'pilot_in_command', 'PIC'
        SIC = 'second_in_command', 'SIC'
        SOLO = 'solo', 'Solo'
        DUAL = 'dual', 'Dual'
        CFI = 'instructor', 'CFI'
        SIM = 'simulator', 'Sim'
        XC = 'cross_country', 'Cross-country'

    condition = models.CharField(max_length=17, choices=FlightCondition.choices, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=80)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    ipc_category = models.CharField(max_length=1, choices=(('A', 'Airplane'), ('R', 'Helicopter')), blank=True, default='')
    ipc_completed_date = models.DateField(blank=True, null=True)
    instructor_period_start = models.DateField(blank=True, null=True)
    last_qualifying_date = models.DateField(blank=True, null=True)
    completion_type = models.CharField(max_length=24, choices=CompletionType.choices, blank=True)
    due_date = models.DateField(blank=True, null=True)
    target_hours = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    aircraft = models.ForeignKey('flights.Aircraft', on_delete=models.CASCADE, blank=True, null=True)
    crew_position = models.CharField(max_length=17, choices=CrewPosition.choices, blank=True)
    company = models.CharField(max_length=50, blank=True)
    company_start_date = models.DateField(blank=True, null=True)
    company_end_date = models.DateField(blank=True, null=True)
    dismissed_key = models.CharField(max_length=48, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=condition, name=name)
                       for name, condition in reminder_conditions()] + [
            models.UniqueConstraint(fields=['user'], condition=models.Q(kind='flight_review'),
                                    name='reminder_user_flight_review_unique'),
        ]

    @property
    def is_dated(self):
        return self.kind in (self.Kind.EXPIRATION, self.Kind.FLIGHT_REVIEW, self.Kind.INSTRUCTOR_RENEWAL, self.Kind.IPC)

    def save(self, *args, **kwargs):
        if self.kind == self.Kind.IPC and self.ipc_completed_date:
            from home.flight_reviews import calendar_month_due_date
            self.due_date = calendar_month_due_date(self.ipc_completed_date, 6)
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'due_date'}
        if self.kind == self.Kind.INSTRUCTOR_RENEWAL and self.instructor_period_start:
            from home.flight_reviews import flight_review_due_date
            self.due_date = flight_review_due_date(self.instructor_period_start)
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'due_date'}
        if self.kind == self.Kind.FLIGHT_REVIEW and self.last_qualifying_date:
            from home.flight_reviews import flight_review_due_date
            self.due_date = flight_review_due_date(self.last_qualifying_date)
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'due_date'}
        return super().save(*args, **kwargs)

    def milestone_progress_label(self, current_hours):
        difference = current_hours - self.target_hours
        delta = f'{difference:+.1f}'.rstrip('0').rstrip('.') if difference else '0'
        return f'{self.milestone_label(current_hours)} | {delta}'

    def milestone_label(self, current_hours=None):
        if self.target_hours is None:
            return 'Set target hours'
        hours = f'{self.target_hours:.1f}'
        if current_hours is not None:
            target = hours.rstrip('0').rstrip('.')
            hours = f'{current_hours:.1f}/{target}'
        if self.kind == self.Kind.FLIGHT_TIME:
            if current_hours is not None:
                return f'Total {hours}'
            return f'{hours} total flight hours'
        if self.kind == self.Kind.FLIGHT_CONDITION:
            return f'{self.get_condition_display()} {hours}'
        if self.kind == self.Kind.COMPANY_TIME:
            if current_hours is not None:
                return f'{self.company} {hours}'
            return f'{hours} hours at {self.company}'
        if not self.aircraft_id:
            return 'Select an aircraft type'
        position = f' {self.get_crew_position_display()}' if self.kind == self.Kind.CREW_IN_TYPE else ''
        if current_hours is not None:
            return f'{self.aircraft.aircraft_type}{position} {hours}'
        return f'{hours}{position} hours in {self.aircraft.aircraft_type}'
