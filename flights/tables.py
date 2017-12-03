import django_tables2 as tables
from .models import *

class TotalTable(tables.Table):
    total=tables.Column(orderable=False)
    total_time=tables.Column(orderable=False)
    pilot_in_command=tables.Column(orderable=False)
    second_in_command=tables.Column(orderable=False)
    cross_country=tables.Column(orderable=False)
    instructor=tables.Column(orderable=False)
    dual=tables.Column(orderable=False)
    solo=tables.Column(orderable=False)
    instrument=tables.Column(orderable=False)
    night=tables.Column(orderable=False)
    simulated_instrument=tables.Column(orderable=False)
    simulator=tables.Column(orderable=False)
    landings_day=tables.Column(orderable=False)
    landings_night=tables.Column(orderable=False)
    landings_total=tables.Column(orderable=False)
    last_flown=tables.Column(orderable=False)
    last_30=tables.Column(orderable=False)
    last_60=tables.Column(orderable=False)
    last_90=tables.Column(orderable=False)
    last_180=tables.Column(orderable=False)
    last_yr=tables.Column(orderable=False)
    last_2yr=tables.Column(orderable=False)
    ydt=tables.Column(orderable=False)

    class Meta:
        model = Total
        data = Total.objects.all()
        attrs = {'class': 'custom-table table table-hover table-sm',
                    'id':'total'}
        exclude = ('id', 'user')

class PowerTable(tables.Table):
    role = tables.Column(orderable=False)
    turbine = tables.Column(orderable=False)
    piston = tables.Column(orderable=False)

    class Meta:
        model = Power
        data = Power.objects.all()
        attrs = {'class': 'table table-hover table-sm'}
        exclude = ('id', 'user')

class RegsTable(tables.Table):
    reg_type = tables.Column(orderable=False)
    pilot_in_command = tables.Column(orderable=False)
    second_in_command = tables.Column(orderable=False)

    class Meta:
        model = Regs
        data = Regs.objects.all()
        attrs = {'class': 'table table-hover table-sm'}
        exclude = ('id', 'user')

class EndrsementTable(tables.Table):
    endorsement = tables.Column(orderable=False)
    total = tables.Column(orderable=False)

    class Meta:
        model = Endorsement
        data = Endorsement.objects.all()
        exclude = ('id', 'user')
        attrs = {'class': 'table table-hover table-sm',
                    'id': 'endorsement'}

class WeightTable(tables.Table):
    weight = tables.Column(orderable=False)
    total = tables.Column(orderable=False)

    class Meta:
        model = Weight
        data = Weight.objects.all()
        exclude = ('id', 'user')
        attrs = {'class': 'table table-hover table-sm',
                    'id': 'weight'}

class StatTable(tables.Table):
    aircraft_type = tables.Column(orderable=False)

    class Meta:
        model = Stat
        data = Stat.objects.all()
        exclude = ('id', 'user')
        attrs = {'class': 'custom-table table table-hover table-sm',
                    'id':'stat'}

class FlightTable(tables.Table):

    route = tables.Column(orderable=False)
    aircraft = tables.Column(orderable=False)
    registration = tables.Column(orderable=False)
    duration = tables.Column(orderable=False)
    landings_day = tables.Column(orderable=False)
    landings_night = tables.Column(orderable=False)
    night = tables.Column(orderable=False)
    instrument = tables.Column(orderable=False)
    approaches = tables.Column(orderable=False)
    cross_country = tables.Column(orderable=False)
    second_in_command = tables.Column(orderable=False)
    pilot_in_command = tables.Column(orderable=False)
    simulated_instrument = tables.Column(orderable=False)
    instructor = tables.Column(orderable=False)
    dual = tables.Column(orderable=False)
    simulator = tables.Column(orderable=False)
    solo = tables.Column(orderable=False)

    class Meta:
        model = Flight
        data = Flight.objects.all()
        exclude = ('id', 'user', 'legs', 'remarks')
        attrs = {'class': 'table table-striped table-hover table-sm'}
