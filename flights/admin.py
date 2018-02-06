from django.contrib import admin
from django.contrib.admin import AdminSite
from .models import *

class FlightAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'aircraft_type', 'registration', 'route', 'duration',
    'landings_day', 'landings_night', 'night', 'instrument', 'approaches',
    'cross_country', 'second_in_command', 'pilot_in_command', 'simulated_instrument',
    'instructor', 'dual', 'simulator', 'solo', 'remarks', 'route_data', 'map_error',
     'duplicate_error', 'aircraft_error', 'tailnumber_error', 'crew_error')
    empty_value_display = ''

class AircraftAdmin(admin.ModelAdmin):
    list_display = ('user', 'aircraft_type', 'turbine', 'piston', 'requires_type',
    'tailwheel', 'compleks', 'high_performance', 'aircraft_category', 'aircraft_class',
     'power_error', 'config_error', 'weight_error', 'category_error', 'class_error')

class TailnumberAdmin(admin.ModelAdmin):
    list_display = ('user', 'registration', 'aircraft', 'is_121', 'is_135', 'is_91', 'error')
    search_fields = ('registration',)
    empty_value_display = ''

class MapDataAdmin(admin.ModelAdmin):
    list_display = ('icao', 'iata', 'name', 'city', 'state', 'country', 'latitude', 'longitude', 'elevation')
    search_fields = ('city', 'state', 'country', 'iata', 'icao')
    empty_value_display = ''

class TotalAdmin(admin.ModelAdmin):
    list_display = ('user', 'total', 'total_time', 'pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator', 'landings_day', 'landings_night', 'landings_total')
    empty_value_display = ''

class StatAdmin(admin.ModelAdmin):
    list_display = ('user', 'aircraft_type', 'total_time')
    empty_value_display = ''

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('comapny', )
    empty_value_display = ''

admin.site.register(Flight, FlightAdmin)
admin.site.register(Aircraft, AircraftAdmin)
admin.site.register(Approach)
admin.site.register(AircraftCategory)
admin.site.register(AircraftClass)
admin.site.register(TailNumber, TailnumberAdmin)
admin.site.register(Total, TotalAdmin)
admin.site.register(Stat, StatAdmin)
admin.site.register(Power)
admin.site.register(Regs)
admin.site.register(Endorsement)
admin.site.register(Weight)
admin.site.register(MapData, MapDataAdmin)
admin.site.register(Profile)
