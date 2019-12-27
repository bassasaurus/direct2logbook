from django.contrib import admin
from .models import *


class CSVAdmin(admin.ModelAdmin):
    list_display = ('user', 'signature')  # add signature
    empty_value_display = ''


admin.site.register(Signature, CSVAdmin)
