from django.contrib import admin
from .models import Profile


class ProfileAdmin(admin.ModelAdmin):
    list_display = (
            'user',
            'pk',
            'customer_id',
            'subscription_id',
            'trial',
            'trial_expiring',
            'active',
            'monthly',
            'yearly',
            'end_date',
            'canceled',
            'expired',
            'company', )  # add signature
    empty_value_display = ''


admin.site.register(Profile, ProfileAdmin)
