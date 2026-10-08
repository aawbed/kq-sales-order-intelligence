from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("<int:notification_id>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
    path("audit-logs/", views.audit_logs, name="audit_logs"),
]
