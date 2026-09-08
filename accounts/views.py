from django.shortcuts import render

from accounts.models import Role
from core.permissions import operations_manager_required, system_administrator_required


@operations_manager_required
def manage_users(request):
    """Figure 3.7j: Manage User Accounts."""
    return render(request, "accounts/manage_users.html")


@system_administrator_required
def edit_user_role(request, user_id):
    """Supports the Manage User Accounts use case (role editing)."""
    raise NotImplementedError
