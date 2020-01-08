from django.contrib import admin
from .models import *


class PDFAdmin(admin.ModelAdmin):
    list_display = ('user', 'signature', 'created_at', 'updated_at')
    empty_value_display = ''


admin.site.register(Signature, PDFAdmin)
