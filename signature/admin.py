from django.contrib import admin
from django.utils.html import format_html
from .models import Signature


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ('user', 'signature_preview')

    def signature_preview(self, obj):
        if obj.signature:
            return format_html(
                '<img src="{}" height="80" style="border:1px solid #ccc"/>',
                obj.signature
            )
        return "No signature"

    signature_preview.short_description = "Signature"
