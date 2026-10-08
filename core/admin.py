from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_id", "recipient", "title", "category", "level", "is_read", "created_at")
    list_filter = ("category", "level", "is_read", "created_at")
    search_fields = ("title", "message", "recipient__username")
