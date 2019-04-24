from django.contrib import admin
from .models import *

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pk', 'company','signature')
    empty_value_display = ''

admin.site.register(Profile, ProfileAdmin)
