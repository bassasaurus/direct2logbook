from django.contrib import admin
from django.contrib.admin import AdminSite
from .models import *

class ApproachInline(admin.TabularInline):
    model = Approach

class HoldingInline(admin.TabularInline):
    model = Holding

class FlightAdmin(admin.ModelAdmin):
    inlines = [
        ApproachInline,
        HoldingInline,
    ]

    list_display = ('pk', 'user', 'date', 'route', 'aircraft_type', 'registration', 'duration',
    'landings_day', 'landings_night', 'night', 'instrument',
    'cross_country', 'second_in_command', 'pilot_in_command', 'simulated_instrument',
    'instructor', 'dual', 'simulator', 'solo', 'remarks', 'route_data', 'map_error',
     'duplicate_error', 'aircraft_type_error', 'registration_error', 'crew_error')
    empty_value_display = ''

class AircraftAdmin(admin.ModelAdmin):
    list_display = ('aircraft_type', 'user', 'pk', 'turbine', 'piston', 'requires_type',
    'tailwheel', 'compleks', 'high_performance', 'aircraft_category', 'aircraft_class', 'image',
     'power_error', 'config_error', 'weight_error', 'category_error', 'class_error')

class TailnumberAdmin(admin.ModelAdmin):
    list_display = ('registration', 'user', 'pk', 'aircraft', 'is_121', 'is_135', 'is_91', 'reg_error')
    search_fields = ('registration',)
    empty_value_display = ''

class MapDataAdmin(admin.ModelAdmin):
    list_display = ('icao', 'iata', 'name', 'city', 'state', 'country', 'latitude', 'longitude', 'elevation')
    search_fields = ('city', 'state', 'country', 'iata', 'icao')
    empty_value_display = ''

class TotalAdmin(admin.ModelAdmin):
    list_display = ('user', 'pk', 'total', 'total_time', 'pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator', 'landings_day', 'landings_night', 'landings_total')
    empty_value_display = ''

class StatAdmin(admin.ModelAdmin):
    list_display = ('user', 'pk', 'aircraft_type', 'total_time')
    empty_value_display = ''

class ApproachAdmin(admin.ModelAdmin):
    list_display = ('flight_object', 'approach_type', 'number')

class HoldingAdmin(admin.ModelAdmin):
    list_display = ('flight_object', 'hold')

class RegAdmin(admin.ModelAdmin):
    list_display = ('user', 'reg_type', 'pilot_in_command', 'second_in_command')

class WeightAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight', 'total')

class PowerAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'turbine', 'piston')

class BulkEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_time', 'pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator', 'landings_day', 'landings_night', 'landings_total', 'last_flown', 'last_30', 'last_60', 'last_90', 'last_yr', 'last_2yr', 'ytd']

admin.site.register(Flight, FlightAdmin)
admin.site.register(Aircraft, AircraftAdmin)

admin.site.register(Holding, HoldingAdmin)
admin.site.register(Approach, ApproachAdmin)

admin.site.register(AircraftCategory)
admin.site.register(AircraftClass)
admin.site.register(TailNumber, TailnumberAdmin)

admin.site.register(Total, TotalAdmin)
admin.site.register(BulkEntry, BulkEntryAdmin)
admin.site.register(Stat, StatAdmin)
admin.site.register(Power, PowerAdmin)
admin.site.register(Regs, RegAdmin)
admin.site.register(Endorsement)
admin.site.register(Weight, WeightAdmin)
admin.site.register(MapData, MapDataAdmin)
