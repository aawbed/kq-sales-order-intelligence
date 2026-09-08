from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    # Figure 3.7h: Sales Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    # Figure 3.7i: Generate Reports
    path("reports/", views.generate_reports, name="generate_reports"),
    # Figure 3.7k: System Settings
    path("settings/", views.system_settings, name="system_settings"),
]
