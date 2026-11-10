from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from datetime import date


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/{1}'.format(instance.user.id, filename)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.CharField(max_length=50, default='', blank=True)

    medical_issue_date = models.DateField(default=date.today)
    first_class = models.BooleanField(default=False)
    second_class = models.BooleanField(default=False)
    third_class = models.BooleanField(default=False)
    over_40 = models.BooleanField(default=False)
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

    def __str__(self):
        title = "{} {}".format(self.user, self.pk)
        return title


class Reminder(models.Model):
    class Kind(models.TextChoices):
        EXPIRATION = 'expiration', 'Expiration date'
        FLIGHT_TIME = 'flight_time', 'Total flight time'
        TIME_IN_TYPE = 'time_in_type', 'Time in Type'
        CREW_IN_TYPE = 'crew_in_type', 'Crew Position in Type'
        COMPANY_TIME = 'company_time', 'Time at Company'

    class CrewPosition(models.TextChoices):
        PIC = 'pilot_in_command', 'PIC'
        SIC = 'second_in_command', 'SIC'
        SOLO = 'solo', 'Solo'
        DUAL = 'dual', 'Dual'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=80)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    due_date = models.DateField(blank=True, null=True)
    target_hours = models.DecimalField(max_digits=6, decimal_places=1, blank=True, null=True)
    aircraft = models.ForeignKey('flights.Aircraft', on_delete=models.SET_NULL, blank=True, null=True)
    crew_position = models.CharField(max_length=17, choices=CrewPosition.choices, blank=True)
    company = models.CharField(max_length=50, blank=True)
    company_start_date = models.DateField(blank=True, null=True)
    company_end_date = models.DateField(blank=True, null=True)
    dismissed_key = models.CharField(max_length=48, blank=True)

    def milestone_label(self, current_hours=None):
        if self.target_hours is None:
            return 'Set target hours'
        hours = f'{self.target_hours:.1f}'
        if current_hours is not None:
            hours = f'{current_hours:.1f} / {hours}'
        if self.kind == self.Kind.FLIGHT_TIME:
            return f'{hours} total flight hours'
        if self.kind == self.Kind.COMPANY_TIME:
            return f'{hours} hours at {self.company}'
        if not self.aircraft_id:
            return 'Select an aircraft type'
        position = f' {self.get_crew_position_display()}' if self.kind == self.Kind.CREW_IN_TYPE else ''
        return f'{hours}{position} hours in {self.aircraft.aircraft_type}'
