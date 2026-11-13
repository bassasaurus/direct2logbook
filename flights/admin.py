from django import forms
from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseRedirect
from django.urls import reverse
from accounts.deletion import account_deletion_resources
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.admin import AdminSite
from .models import *
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User


admin.site.site_title = 'Direct2Logbook Admin'
admin.site.site_header = 'Direct2Logbook Admin'

class EmailRequiredMixin(object):
    def __init__(self, *args, **kwargs):
        super(EmailRequiredMixin, self).__init__(*args, **kwargs)
        # make user email field required
        self.fields['email'].required = True


class MyUserCreationForm(EmailRequiredMixin, UserCreationForm):
    pass


class MyUserChangeForm(EmailRequiredMixin, UserChangeForm):
    pass


class EmailRequiredUserAdmin(UserAdmin):
    form = MyUserChangeForm
    add_form = MyUserCreationForm
    add_fieldsets = ((None, {
        'fields': ('username', 'email', 'password1', 'password2'),
        'classes': ('wide',)
    }),)

    def get_deleted_objects(self, objs, request):
        deleted, counts, permissions, protected = super().get_deleted_objects(objs, request)
        for user in objs:
            try:
                resources = account_deletion_resources(user, user._state.db or 'default')
                user._external_cleanup_required = any(resources)
            except ProtectedError as error:
                protected.append(str(error.args[0]))
        return deleted, counts, permissions, protected

    def delete_model(self, request, obj):
        pending = getattr(obj, '_external_cleanup_required', False)
        super().delete_model(request, obj)
        if pending:
            self.message_user(request, 'Stripe/file cleanup is queued after commit. Check Account deletion cleanups until it completes.', messages.WARNING)

    def delete_queryset(self, request, queryset):
        pending = any(getattr(user, '_external_cleanup_required', False) for user in queryset)
        super().delete_queryset(request, queryset)
        if pending:
            self.message_user(request, 'Stripe/file cleanup is queued after commit. Check Account deletion cleanups until it completes.', messages.WARNING)

    def delete_view(self, request, object_id, extra_context=None):
        try:
            return super().delete_view(request, object_id, extra_context)
        except ProtectedError as error:
            # A billing task may claim the account after the confirmation page loads.
            self.message_user(request, str(error.args[0]), messages.ERROR)
            return HttpResponseRedirect(reverse('admin:auth_user_change', args=[object_id]))

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context)
        except ProtectedError as error:
            self.message_user(request, str(error.args[0]), messages.ERROR)
            return HttpResponseRedirect(reverse('admin:auth_user_changelist'))


admin.site.unregister(User)
admin.site.register(User, EmailRequiredUserAdmin)


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

    list_filter = ('user',)
    search_fields = ['route',]

class AircraftAdmin(admin.ModelAdmin):
    list_display = ('aircraft_type', 'user', 'pk', 'turbine', 'piston', 'requires_type',
    'tailwheel', 'compleks', 'high_performance', 'aircraft_category', 'aircraft_class', 'image')

    list_filter = ('user',)

class TailnumberAdminForm(forms.ModelForm):
    is_121 = forms.BooleanField(required=False, label='Is 121')
    is_135 = forms.BooleanField(required=False, label='Is 135')
    is_91 = forms.BooleanField(required=False, label='Is 91')

    class Meta:
        model = TailNumber
        fields = '__all__'


class TailnumberAdmin(admin.ModelAdmin):
    form = TailnumberAdminForm

    def get_changelist_form(self, request, **kwargs):
        return super().get_changelist_form(request, **{'form': self.form, **kwargs})

    list_display = ('registration', 'user', 'pk', 'aircraft', 'is_121', 'is_135', 'is_91')
    list_display_links = ('pk',)
    list_editable = ('registration', 'is_121', 'is_135', 'is_91')
    search_fields = ('registration',)
    empty_value_display = ''

    list_filter = ('user',)

class MapDataAdmin(admin.ModelAdmin):
    list_display = ('icao', 'iata', 'name', 'city', 'state', 'country', 'airport_type', 'ourairports_id')
    search_fields = ('city', 'state', 'country', 'iata', 'icao', 'codes__code')
    empty_value_display = ''

class TotalAdmin(admin.ModelAdmin):
    list_display = ('user', 'pk', 'total', 'total_time', 'pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator', 'landings_day', 'landings_night', 'landings_total')
    empty_value_display = ''

    list_filter = ('user',)

class StatAdmin(admin.ModelAdmin):
    list_display = ('user', 'pk', 'aircraft_type', 'total_time')
    empty_value_display = ''

    list_filter = ('user',)

class ApproachAdmin(admin.ModelAdmin):
    list_display = ('flight_object', 'approach_type', 'number')


class HoldingAdmin(admin.ModelAdmin):
    list_display = ('flight_object', 'hold')


class RegAdmin(admin.ModelAdmin):
    list_display = ('user', 'reg_type', 'pilot_in_command', 'second_in_command')

    list_filter = ('user',)

class WeightAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight', 'total')

    list_filter = ('user',)

class PowerAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'turbine', 'piston')

    list_filter = ('user',)

# admin.site.unregister(User)
# admin.site.register(User, UserAdmin)
admin.site.register(Flight, FlightAdmin)
admin.site.register(Aircraft, AircraftAdmin)

admin.site.register(Holding, HoldingAdmin)
admin.site.register(Approach, ApproachAdmin)

# admin.site.register(AircraftCategory)
# admin.site.register(AircraftClass)
admin.site.register(TailNumber, TailnumberAdmin)

admin.site.register(Imported)
admin.site.register(Total, TotalAdmin)
admin.site.register(Stat, StatAdmin)
admin.site.register(Power, PowerAdmin)
admin.site.register(Regs, RegAdmin)
admin.site.register(Endorsement)
admin.site.register(Weight, WeightAdmin)
admin.site.register(MapData, MapDataAdmin)
