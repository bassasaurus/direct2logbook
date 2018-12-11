import re
from django.db import models
from django.db import signals
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.auth.models import User, Group

from picklefield.fields import PickledObjectField

from django.template.defaultfilters import truncatechars  # or truncatewords

from django.core.validators import MinValueValidator, RegexValidator


BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))

positive_validator = MinValueValidator(0.0, "Must be a positive number > 0.1")

route_match = r'((?:[A-Z]{3,4}\-?)+)'
route_validator = RegexValidator(route_match, "Must be UPPERCASE in a combination of ATA-ICAO")

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.CharField(max_length=50, default='')

    def __str__(self):
        title = str(self.user)
        return title

#FAA data from http://www.faa.gov/airports/airport_safety/airportdata_5010/menu/nfdcfacilitiesexport.cfm?Region=&District=&State=&County=&City=&Use=PU&Certification=
class MapData(models.Model):
    name = models.CharField(max_length=50, default='')
    city = models.CharField(db_index=True, max_length=50, default='')
    state = models.CharField(db_index=True, max_length=50, default='')
    country = models.CharField(db_index=True, max_length=50, default='')
    iata = models.CharField(db_index=True, max_length=3, default='')
    icao = models.CharField(db_index=True, max_length=4, default='')
    latitude = models.FloatField(null=True, blank=True, default=0)
    longitude = models.FloatField(null=True, blank=True, default=0)
    elevation = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        ordering = ['city', 'state', 'country']
        verbose_name_plural = "Map Data"
        index_together = ['iata', 'icao']

class Stat(models.Model):
    user = models.ForeignKey(User, default=1)
    aircraft_type = models.CharField(max_length=10)
    total_time = models.DecimalField(decimal_places=1, max_digits=6,null=False, blank=True, default=0, verbose_name="Time")
    pilot_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="SIC")
    cross_country = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="XC")
    instructor = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0 , verbose_name="CFI")
    dual = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)
    solo = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)
    instrument = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="Inst")
    night = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)
    simulated_instrument = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="Sim Inst")
    simulator = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="Sim")
    landings_day = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Night Ldg")
    last_flown = models.DateField(db_index=True, null=True, blank=True)
    last_30 = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='30')
    last_60 = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='60')
    last_90 = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='90')
    last_180 = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='6mo')
    last_yr = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='12mo')
    last_2yr = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='24')
    ytd = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='YDT')


    class Meta:
        ordering = ["-last_flown"]

    def __str__(self):
        title = str(self.aircraft_type)
        return title

class Total(models.Model):
    user = models.ForeignKey(User, default=1)
    total = models.CharField(max_length=20, default='')
    total_time = models.DecimalField(decimal_places=1, max_digits=6, db_index=True, null=True, blank=True, default=0, verbose_name="Time")
    pilot_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="SIC")
    cross_country = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="XC")
    instructor = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="CFI")
    dual = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    solo = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    instrument = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="Inst")
    night = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0)
    simulated_instrument = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="Sim Inst")
    simulator = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, default=0, verbose_name="Sim")
    landings_day = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Night Ldg")
    landings_total = models.PositiveIntegerField(null=True, blank=True, default=0, verbose_name="Total Ldg")
    last_flown = models.DateField(null=True, blank=True)
    last_30 = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='30')
    last_60 = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='60')
    last_90 = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='90')
    last_180 = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='6mo')
    last_yr = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='12mo')
    last_2yr = models.DecimalField(decimal_places=1, max_digits=6, null=True, blank=True, verbose_name='24')
    ytd = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, verbose_name='YDT')

    class Meta:
        ordering = ['-total_time']

    def __str__(self):
        title = str(self.total) + ' ' + str(self.total_time)
        return title

class Power(models.Model):
    user = models.ForeignKey(User, default=1)
    role = models.CharField(db_index=True, max_length=5, default='')
    turbine = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)
    piston = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)

    class Meta:
        verbose_name_plural = "Power"
        ordering = ['-role']

    def __str__(self):
        title = str(self.role)
        return title

class Regs(models.Model):
    user = models.ForeignKey(User, default=1)
    reg_type = models.CharField(db_index=True, max_length=5, default='', verbose_name="Reg")
    pilot_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="PIC")
    second_in_command = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0, verbose_name="SIC")

    class Meta:
        verbose_name_plural = "Regs"

    def __str__(self):
        title = str(self.reg_type)
        return title

class Endorsement(models.Model):
    user = models.ForeignKey(User, default=1)
    endorsement = models.CharField(max_length=30, default='')
    total = models.DecimalField(decimal_places=1, max_digits=6,db_index=True, null=True, blank=True, default=0)

    class Meta:
        ordering = ['-total']

    def __str__(self):
        title = str(self.endorsement) + ' ' + str(self.total)
        return title

class Weight(models.Model):
    user = models.ForeignKey(User, default=1)
    weight = models.CharField(max_length=20, default='')
    total = models.DecimalField(decimal_places=1, max_digits=6,null=True, blank=True, default=0)

    class Meta:
        verbose_name_plural = "Weight"

    def __str__(self):
        title = str(self.weight) + ' ' + str(self.total)
        return title

class Aircraft(models.Model):
    user = models.ForeignKey(User, default=1)
    aircraft_type = models.CharField(db_index=True, max_length=10, unique=True)
    turbine = models.NullBooleanField()
    piston = models.NullBooleanField()
    requires_type = models.NullBooleanField()
    tailwheel = models.NullBooleanField()
    simple = models.NullBooleanField()
    compleks = models.NullBooleanField(verbose_name='Complex')
    high_performance = models.NullBooleanField()
    aircraft_category = models.ForeignKey('AircraftCategory', default=None, null=True, blank=True)
    aircraft_class = models.ForeignKey('AircraftClass', default=None, null=True, blank=True)
    superr = models.NullBooleanField(verbose_name = 'Super')
    heavy = models.NullBooleanField(verbose_name = 'Heavy >300k lbs')
    large = models.NullBooleanField(verbose_name = 'Large 41k-300k lbs')
    medium = models.NullBooleanField(verbose_name = 'Meduim 12.5-41k lbs')
    small = models.NullBooleanField(verbose_name = 'Small <12.5k lbs')
    light_sport = models.NullBooleanField(verbose_name = 'LSA <1320 lbs')
    # file will be uploaded to MEDIA_ROOT/aircraft
    image = models.FileField(upload_to='aircraft/', default=None, null=True, blank=True)
    config_error = models.CharField(max_length=100, null=True, blank=True)
    power_error = models.CharField(max_length=100, null=True, blank=True)
    weight_error = models.CharField(max_length=100, null=True, blank=True)
    category_error = models.CharField(max_length=100, null=True, blank=True)
    class_error = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["aircraft_type"]
        verbose_name_plural = "Aircraft"

    def __str__(self):
        aircraft_type = str(self.aircraft_type)
        return aircraft_type


class Flight(models.Model):
    user = models.ForeignKey(User, default=1)
    date = models.DateField(db_index=True)
    aircraft_type = models.ForeignKey('Aircraft', default=None, null=True, blank=True, on_delete=models.SET_NULL)
    registration = models.ForeignKey('TailNumber', default=None, null=True, blank=True, on_delete=models.SET_NULL)
    route = models.CharField(max_length=50, )
    legs = models.PositiveIntegerField(null=True)
    duration = models.DecimalField(decimal_places=1, max_digits=3, null=True, validators=[positive_validator])
    landings_day = models.PositiveIntegerField(null=True, blank=True, verbose_name="Day Ldg")
    landings_night = models.PositiveIntegerField(null=True, blank=True, verbose_name="Night Ldg")
    night = models.FloatField(null=True, blank=True, validators=[positive_validator])
    instrument = models.FloatField(null=True, blank=True, verbose_name="Inst", validators=[positive_validator])
    cross_country = models.NullBooleanField(null=True, blank=True, verbose_name="XCountry")
    second_in_command = models.NullBooleanField(null=True, blank=True, verbose_name="SIC")
    pilot_in_command = models.NullBooleanField(null=True, blank=True, verbose_name="PIC")
    simulated_instrument = models.FloatField(null=True, blank=True, verbose_name="Sim Inst", validators=[positive_validator])
    instructor = models.NullBooleanField(null=True, blank=True, verbose_name="CFI")
    dual = models.NullBooleanField(null=True, blank=True)
    remarks = models.CharField(max_length=500, null=True, blank=True)
    simulator = models.NullBooleanField(null=True, blank=True, verbose_name="Sim")
    solo = models.NullBooleanField(null=True, blank=True)

    route_data = PickledObjectField(null=True, blank=True)
    map_error = models.CharField(max_length=100, null=True, blank=True)
    duplicate_error = models.CharField(max_length=100, null=True, blank=True)
    aircraft_type_error = models.CharField(max_length=100, null=True, blank=True)
    registration_error = models.CharField(max_length=100, null=True, blank=True)
    crew_error = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        index_together = ['route', 'date', 'duration']

    def get_absolute_url(self):
        return reverse('flight_detail', kwargs={'pk': self.pk})

class TailNumber(models.Model):
    user = models.ForeignKey(User, default=1)
    registration = models.CharField(db_index=True, max_length=10)
    aircraft = models.ForeignKey('Aircraft', default=None, blank=False)
    is_121 = models.NullBooleanField(null=True, blank=True)
    is_135 = models.NullBooleanField(null=True, blank=True)
    is_91 = models.NullBooleanField(null=True, blank=True)

    reg_error = models.CharField(null=True, blank=True, max_length=50)

    class Meta:
        ordering =['aircraft']
        verbose_name_plural = "Tailnumbers"

    def __str__(self):
        registration = str(self.registration)
        return registration

class Approach(models.Model):

    APPR_CHOICES=(
        ('ILS', 'ILS'),
        ('CATII', 'CAT II'),
        ('CATIII', 'CAT III'),
        ('GPS', 'GPS'),
        ('RNAV', 'RNAV'),
        ('LOC', 'LOC'),
        ('VOR', 'VOR'),
        ('NDB', 'NDB'),
        ('LOC BC', 'LOC BC'),

        ('SDF', 'SDF'),
        ('LDA', 'LDA'),
        ('TACAN', 'TACAN'),
        ('MLS', 'MLS'),
        )

    flight_object = models.ForeignKey('Flight', default=None, null=True, blank=True, verbose_name="Flight", on_delete=models.SET_NULL)
    approach_type = models.CharField(max_length=15, choices=APPR_CHOICES, verbose_name="Approach Type")
    number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Number")

    class Meta:
        ordering =['approach_type']
        verbose_name_plural = "Approaches"

    def __str__(self):
        return self.approach_type

class Holding(models.Model):

    flight_object = models.ForeignKey('Flight', default=None, null=True, blank=True, verbose_name="Flight", on_delete=models.SET_NULL)
    hold = models.NullBooleanField(null=True, blank=True)
    hold_number = models.PositiveIntegerField(null=True, blank=True, verbose_name="Number")

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
