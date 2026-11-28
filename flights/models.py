
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse

from django.contrib.auth.models import User

from picklefield.fields import PickledObjectField

from django.core.validators import MinValueValidator, RegexValidator
from flights.aircraft_classification import CATEGORY_CHOICES, CLASS_CHOICES
from flights.launch_methods import LAUNCH_CHOICES
from flights.remarks import validate_remarks


BOOL_CHOICES = ((True, 'Yes'), (False, 'No', None, ''))

positive_validator = MinValueValidator(0, "Must be a positive number > 0.1")

route_match = r'((?:[A-Z]{3,4}\-?)+)'
route_validator = RegexValidator(
    route_match, "Must be UPPERCASE in a combination of ATA-ICAO")


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/{1}'.format(instance.user.id, filename)

# FAA data from http://www.faa.gov/airports/airport_safety/airportdata_5010/menu/nfdcfacilitiesexport.cfm?Region=&District=&State=&County=&City=&Use=PU&Certification=


class MapData(models.Model):
    name = models.CharField(max_length=500, default='')
    city = models.CharField(db_index=True, max_length=500, default='')
    state = models.CharField(db_index=True, max_length=500, default='')
    country = models.CharField(db_index=True, max_length=500, default='')
    iata = models.CharField(db_index=True, max_length=4, default='')
    icao = models.CharField(db_index=True, max_length=4, default='')
    latitude = models.FloatField(null=True, blank=True, default=0)
    longitude = models.FloatField(null=True, blank=True, default=0)
    elevation = models.IntegerField(null=True, blank=True, default=0)

    ourairports_id = models.PositiveIntegerField(null=True, blank=True, unique=True, editable=False)
    ourairports_ident = models.CharField(max_length=40, blank=True, default='', editable=False)
    airport_type = models.CharField(max_length=30, blank=True, default='', editable=False)

    class Meta:
        ordering = ['city', 'state', 'country']
        verbose_name_plural = "Map Data"
        indexes = [
            models.Index(fields=['iata']),
            models.Index(fields=['icao']),
        ]


class AirportCode(models.Model):
    airport = models.ForeignKey(MapData, on_delete=models.CASCADE, related_name='codes')
    code = models.CharField(max_length=12, db_index=True)
    kind = models.CharField(max_length=10)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['airport', 'code', 'kind'], name='airport_code_kind_unique')]


class Stat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aircraft_type = models.CharField(max_length=10)
    total_time = models.DecimalField(
        decimal_places=1, max_digits=6, null=False, blank=True, default=0, verbose_name="Time")
    pilot_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="SIC")
    cross_country = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="XC")
    instructor = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="CFI")
    dual = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    solo = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Inst")
    night = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    simulated_instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim Inst")
    simulator = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim")
    landings_day = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Night Ldg")
    last_flown = models.DateField(db_index=True, null=True, blank=True)
    last_30 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='30')
    last_60 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='60')
    last_90 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='90')
    last_180 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='6mo')
    last_yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='12mo')
    last_2yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='24')
    ytd = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='YDT')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'aircraft_type'], name='stat_user_aircraft_unique')]
        ordering = ['user', '-last_flown']

    def __str__(self):
        title = str(self.aircraft_type)
        return title


class Total(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.CharField(max_length=20, default='')
    total_time = models.DecimalField(
        decimal_places=1, max_digits=6, db_index=True, null=True, blank=True, default=0, verbose_name="Time")
    pilot_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="SIC")
    cross_country = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="XC")
    instructor = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="CFI")
    dual = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    solo = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Inst")
    night = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    simulated_instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim Inst")
    simulator = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim")
    landings_day = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Night Ldg")
    landings_total = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Total Ldg")
    last_flown = models.DateField(null=True, blank=True)
    last_30 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='30')
    last_60 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='60')
    last_90 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='90')
    last_180 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='6mo')
    last_yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='12mo')
    last_2yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='24')
    ytd = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='YDT')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'total'], name='total_user_category_unique')]
        ordering = ['user', '-total_time']

    def __str__(self):
        title = str(self.total) + ' ' + str(self.total_time)
        return title


class Power(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(db_index=True, max_length=5, default='')
    turbine = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    piston = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    electric = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'role'], name='power_user_role_unique')]
        verbose_name_plural = "Power"
        ordering = ['user', '-role']

    def __str__(self):
        title = str(self.role)
        return title


class Regs(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reg_type = models.CharField(db_index=True, max_length=5, default='')
    pilot_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="SIC")

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'reg_type'], name='regs_user_type_unique')]
        verbose_name_plural = "Regs"
        ordering = ['user']

    def __str__(self):
        title = str(self.reg_type)
        return title


class Endorsement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    endorsement = models.CharField(max_length=30, default='')
    total = models.DecimalField(
        decimal_places=1, max_digits=6, db_index=True, null=True, blank=True, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'endorsement'], name='endorsement_user_kind_unique')]
        ordering = ['user', '-total']

    def __str__(self):
        title = str(self.endorsement) + ' ' + str(self.total)
        return title


class Weight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    weight = models.CharField(max_length=20, default='')
    total = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'weight'], name='weight_user_category_unique')]
        verbose_name_plural = "Weight"
        ordering = ['user']

    def __str__(self):
        title = str(self.weight) + ' ' + str(self.total)
        return title


class Aircraft(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aircraft_type = models.CharField(db_index=True, max_length=10)
    is_default = models.BooleanField(default=False)
    default_crew_role = models.CharField(max_length=3, blank=True, default='',
        choices=[('PIC', 'PIC'), ('SIC', 'SIC')])
    default_cross_country = models.BooleanField(default=False)
    turbine = models.BooleanField(default=False)
    piston = models.BooleanField(default=False)
    electric = models.BooleanField(default=False)
    self_launch_capable = models.BooleanField(default=False)
    requires_type = models.BooleanField(default=False)
    tailwheel = models.BooleanField(default=False)
    # Retired UI choice; retain historical aircraft flags and summary reconciliation.
    simple = models.BooleanField(default=False)
    compleks = models.BooleanField(default=False, verbose_name='Complex')
    high_performance = models.BooleanField(default=False)

    aircraft_category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, verbose_name="Aircraft Category", default='')
    aircraft_class = models.CharField(
        max_length=30, choices=CLASS_CHOICES, verbose_name="Aircraft Class", default='', blank=True)

    superr = models.BooleanField(default=False, verbose_name='Super')
    heavy = models.BooleanField(default=False, verbose_name='Heavy ≥300,000 lbs')
    large = models.BooleanField(
        default=False, verbose_name='Large >41,000 and <300,000 lbs')
    small = models.BooleanField(default=False, verbose_name='Small ≤41,000 lbs')
    # file will be uploaded to MEDIA_ROOT/aircraft
    image = models.FileField(upload_to='aircraft/',
                             default=None, null=True, blank=True)

    class Meta:
        ordering = ['user', 'aircraft_type']
        verbose_name_plural = "Aircraft"
        constraints = [
            models.CheckConstraint(condition=models.Q(default_crew_role__in=['', 'PIC', 'SIC']),
                                   name='aircraft_default_crew_role_valid'),
            models.UniqueConstraint(fields=['user'], condition=models.Q(is_default=True),
                                    name='one_default_aircraft_per_user'),
            models.UniqueConstraint(Lower('aircraft_type'), 'user', name='aircraft_user_type_ci_unique'),
            models.UniqueConstraint(fields=['user', 'id'], name='aircraft_owner_id_unique'),
            models.CheckConstraint(condition=~models.Q(aircraft_type__regex=r'^\s*$'),
                                   name='aircraft_type_nonempty'),
        ]

    def __str__(self):
        aircraft_type = str(self.aircraft_type)
        return aircraft_type

    @property
    def class_display(self):
        from flights.aircraft_classification import class_display
        return class_display(self.aircraft_category, self.aircraft_class)

    @property
    def engine_type_required(self):
        from flights.aircraft_characteristics import engine_required
        return engine_required(self.aircraft_category, self.aircraft_class)

    @property
    def class_required(self):
        from flights.aircraft_classification import class_required
        return class_required(self.aircraft_category)

    def can_delete(self):
        return not (
            TailNumber.objects.filter(aircraft=self).exists()
            or Flight.objects.filter(aircraft_type=self).exists()
            or Imported.objects.filter(aircraft_type=self).exists()
        )


class Flight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(db_index=True)
    aircraft_type = models.ForeignKey(
        'Aircraft', default=None, on_delete=models.CASCADE)
    registration = models.ForeignKey(
        'TailNumber', default=None, null=True, blank=True, on_delete=models.CASCADE)
    route = models.CharField(max_length=50, blank=True)
    launch_method = models.CharField(max_length=8, blank=True, default='', choices=LAUNCH_CHOICES)
    duration = models.DecimalField(
        decimal_places=1, max_digits=3, null=True, validators=[positive_validator])
    landings_day = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Night Ldg")
    night = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True,
                              validators=[positive_validator])
    instrument = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, verbose_name="Inst", validators=[positive_validator])
    cross_country = models.BooleanField(
        default=False, blank=True, verbose_name="XCountry")
    second_in_command = models.BooleanField(
        default=False, blank=True, verbose_name="SIC")
    pilot_in_command = models.BooleanField(
        default=False, blank=True, verbose_name="PIC")
    simulated_instrument = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True, verbose_name="Sim Inst", validators=[positive_validator])
    instructor = models.BooleanField(
        default=False, blank=True, verbose_name="CFI")
    dual = models.BooleanField(default=False, blank=True)
    remarks = models.CharField(max_length=500, null=True, blank=True, validators=[validate_remarks])
    simulator = models.BooleanField(
        null=True, blank=True, verbose_name="Sim")
    class DeviceType(models.TextChoices):
        FFS = 'FFS', 'FFS — Full Flight Simulator'
        FTD = 'FTD', 'FTD — Flight Training Device'
        ATD = 'ATD', 'ATD — Aviation Training Device'

    device_type = models.CharField(max_length=3, choices=DeviceType.choices, blank=True, default='')
    device_id = models.CharField(max_length=100, blank=True, default='', verbose_name='Device ID')
    atd_type = models.CharField(max_length=4, blank=True, default='', choices=[('BATD', 'BATD'), ('AATD', 'AATD')])
    instrument_credit_eligible = models.BooleanField(default=False)
    solo = models.BooleanField(default=False, blank=True)
    hold = models.BooleanField(
        default=False, blank=True, verbose_name="Hold")
    night_landings_full_stop = models.BooleanField(null=True, blank=True, default=None)
    route_airport_choices = models.JSONField(default=dict, blank=True, editable=False)
    route_data = PickledObjectField(null=True, blank=True)
    map_error = models.CharField(max_length=100, null=True, blank=True)
    duplicate_error = models.CharField(max_length=100, null=True, blank=True)
    aircraft_type_error = models.CharField(
        max_length=100, null=True, blank=True)
    registration_error = models.CharField(
        max_length=100, null=True, blank=True)
    crew_error = models.CharField(max_length=100, null=True, blank=True)
    app_markers = models.JSONField(default=str, blank=True)
    app_polylines = models.JSONField(default=str, blank=True)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from flights.launch_methods import validate_launch_method
        errors = validate_launch_method({}, self)
        if errors:
            raise ValidationError(errors)

    class Meta:
        ordering = ['-date', 'pk']
        indexes = [
            models.Index(fields=['route', 'date', 'duration']),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(simulator=True, simulator__isnull=False) | ~models.Q(route__regex=r'^\s*$'), name='flight_route_nonempty'),
            models.CheckConstraint(condition=models.Q(simulator=True, simulator__isnull=False) | models.Q(registration__isnull=False), name='flight_registration_required'),
            models.CheckConstraint(condition=models.Q(device_type__in=['', 'FFS', 'FTD', 'ATD']), name='flight_device_type_valid'),
            models.CheckConstraint(condition=models.Q(launch_method__in=['', 'AEROTOW', 'GROUND', 'SELF']), name='flight_launch_method_valid'),
            models.CheckConstraint(condition=(
                (models.Q(duration__gte=0) | models.Q(duration__isnull=True))
                & (models.Q(night__gte=0) | models.Q(night__isnull=True))
                & (models.Q(instrument__gte=0) | models.Q(instrument__isnull=True))
                & (models.Q(simulated_instrument__gte=0) | models.Q(simulated_instrument__isnull=True))
            ), name='flight_hours_nonnegative'),
        ]

    def save(self, *args, **kwargs):
        from flights.route_normalization import normalize_route
        if kwargs.get('update_fields') is None or 'remarks' in kwargs['update_fields']:
            from django.core.exceptions import ValidationError
            try:
                validate_remarks(self.remarks)
            except ValidationError as exc:
                raise ValidationError({'remarks': exc.messages}) from exc
        if kwargs.get('update_fields') is None or 'route' in kwargs['update_fields']:
            original_route = self.route
            self.route = normalize_route(self.route)
            if self.route != original_route and isinstance(self.route_airport_choices, dict) and self.route_airport_choices.get('route') == original_route:
                self.route_airport_choices = {**self.route_airport_choices, 'route': self.route}
                if kwargs.get('update_fields') is not None:
                    kwargs['update_fields'] = set(kwargs['update_fields']) | {'route_airport_choices'}
        if not isinstance(self.route_airport_choices, dict):
            self.route_airport_choices = {}
        if self.route_airport_choices and self.route_airport_choices.get('route') != self.route:
            self.route_airport_choices = {}
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'route_airport_choices'}
        return super().save(*args, **kwargs)

    @property
    def distance_nm(self):
        from flights.mileage import route_distance_nm
        return route_distance_nm(self)

    @property
    def validation_errors(self):
        from flights.error_checks import flight_error_messages
        return flight_error_messages(self)

    @property
    def has_errors(self):
        return bool(self.validation_errors)

    def get_absolute_url(self):
        return reverse('flight_detail', kwargs={'pk': self.pk})

    def __str__(self):
        from logbook.date_formats import display_date
        return "{} | {}".format(display_date(self.date), self.route)


class TailNumber(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registration = models.CharField(db_index=True, max_length=10)
    aircraft = models.ForeignKey(
        'Aircraft', on_delete=models.CASCADE, default=None)
    is_121 = models.BooleanField(null=True, blank=True)
    is_135 = models.BooleanField(null=True, blank=True)
    is_91 = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Tailnumbers"
        ordering = ['user', 'aircraft', 'registration']
        constraints = [
            models.UniqueConstraint(Lower('registration'), 'user', name='tailnumber_user_reg_ci_unique'),
            models.UniqueConstraint(fields=['user', 'id'], name='tailnumber_owner_id_unique'),
            models.UniqueConstraint(fields=['id', 'aircraft'], name='tailnumber_id_aircraft_unique'),
            models.CheckConstraint(condition=~models.Q(registration__regex=r'^\s*$'),
                                   name='tailnumber_reg_nonempty'),
        ]

    def __str__(self):
        registration = str(self.registration)
        return registration

    def get_absolute_url(self):
        return reverse('tailnumber_detail', kwargs={'pk': self.pk})

    def can_delete(self):
        return not Flight.objects.filter(registration=self).exists()


class Approach(models.Model):

    from flights.approach_choices import ALL_APPROACH_CHOICES
    APPR_CHOICES = ALL_APPROACH_CHOICES

    flight_object = models.ForeignKey(
        'Flight', default=None, null=True, blank=True, verbose_name="Flight", on_delete=models.CASCADE)
    approach_type = models.CharField(
        max_length=15, choices=APPR_CHOICES, verbose_name="Approach Type")
    number = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Number")

    class Meta:
        verbose_name_plural = "Approaches"
        ordering = ['approach_type']

    def __str__(self):
        return str(self.approach_type)


class Holding(models.Model):

    flight_object = models.ForeignKey(
        'Flight', default=None, null=True, blank=True, verbose_name="Flight", on_delete=models.CASCADE)
    hold = models.BooleanField(blank=True, default=False)


class AircraftCategory(models.Model):
    aircraft_category = models.CharField(max_length=30)

    class Meta:
        verbose_name_plural = "Aircraft Categories"

    def __str__(self):
        return self.aircraft_category


class AircraftClass(models.Model):
    aircraft_class = models.CharField(max_length=30)

    class Meta:
        verbose_name_plural = "Aircraft Classes"

    def __str__(self):
        return self.aircraft_class


class Imported(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    aircraft_type = models.ForeignKey(Aircraft, on_delete=models.CASCADE)
    is_121 = models.BooleanField(null=True, blank=True)
    is_135 = models.BooleanField(null=True, blank=True)
    is_91 = models.BooleanField(null=True, blank=True)
    total_time = models.DecimalField(
        decimal_places=1, max_digits=6, db_index=True, null=True, blank=True, default=0, verbose_name="Time")
    pilot_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="SIC")
    cross_country = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="XC")
    instructor = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="CFI")
    dual = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    solo = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Inst")
    night = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    simulated_instrument = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim Inst")
    simulator = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim")
    landings_day = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Night Ldg")
    landings_total = models.PositiveIntegerField(
        null=True, blank=True, default=0, verbose_name="Total Ldg")
    last_flown = models.DateField(null=True, blank=True)
    last_30 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='30')
    last_60 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='60')
    last_90 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='90')
    last_180 = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='6mo')
    last_yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='12mo')
    last_2yr = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='24')
    ytd = models.DecimalField(
        decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='YTD')

    class Meta:
        verbose_name_plural = "Imported"
        constraints = [models.CheckConstraint(condition=(
                (models.Q(total_time__gte=0) | models.Q(total_time__isnull=True))
                & (models.Q(pilot_in_command__gte=0) | models.Q(pilot_in_command__isnull=True))
                & (models.Q(second_in_command__gte=0) | models.Q(second_in_command__isnull=True))
                & (models.Q(cross_country__gte=0) | models.Q(cross_country__isnull=True))
                & (models.Q(instructor__gte=0) | models.Q(instructor__isnull=True))
                & (models.Q(dual__gte=0) | models.Q(dual__isnull=True))
                & (models.Q(solo__gte=0) | models.Q(solo__isnull=True))
                & (models.Q(instrument__gte=0) | models.Q(instrument__isnull=True))
                & (models.Q(night__gte=0) | models.Q(night__isnull=True))
                & (models.Q(simulated_instrument__gte=0) | models.Q(simulated_instrument__isnull=True))
                & (models.Q(simulator__gte=0) | models.Q(simulator__isnull=True))
        ), name='imported_hours_nonnegative')]

    def __str__(self):
        title = str(self.aircraft_type)
        return title

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)
