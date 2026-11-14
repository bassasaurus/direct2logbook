from django.contrib import admin
from django.utils import timezone

from .deletion import publish_cleanup
from .models import AccountDeletionCleanup


@admin.register(AccountDeletionCleanup)
class AccountDeletionCleanupAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'attempts', 'next_attempt_at', 'last_error')
    readonly_fields = ('id', 'customer_ids', 'subscription_ids', 'media_names',
                       'attempts', 'last_error', 'next_attempt_at', 'created_at')
    actions = ['retry_cleanup']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Retry selected account cleanups')
    def retry_cleanup(self, request, queryset):
        queryset.update(next_attempt_at=timezone.now())
        for cleanup_id in queryset.values_list('pk', flat=True):
            publish_cleanup(str(cleanup_id))
        self.message_user(
            request, 'Cleanup retries requested. Pending records remain until cleanup succeeds.')
