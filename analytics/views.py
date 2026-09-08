from django.shortcuts import render

from core.permissions import operations_manager_required, system_administrator_required


@operations_manager_required
def dashboard(request):
    """Figure 3.7h: Operations Manager — Sales Dashboard."""
    return render(request, "analytics/dashboard.html")


@operations_manager_required
def generate_reports(request):
    """Figure 3.7i: Operations Manager — Generate Reports."""
    return render(request, "analytics/generate_reports.html")


@system_administrator_required
def system_settings(request):
    """Figure 3.7k: System Administrator — System Settings."""
    return render(request, "analytics/system_settings.html")
