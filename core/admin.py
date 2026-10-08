from django.contrib import admin
from .models import AuditLog, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_id", "recipient", "title", "category", "level", "is_read", "created_at")
    list_filter = ("category", "level", "is_read", "created_at")
    search_fields = ("title", "message", "recipient__username")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "target_model", "target_id", "ip_address")
    list_filter = ("action", "target_model", "timestamp")
    search_fields = ("user__username", "target_id", "details", "ip_address")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
