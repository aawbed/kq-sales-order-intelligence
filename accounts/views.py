from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import SystemUserCreationForm
from accounts.models import Role, User
from core.permissions import operations_manager_required, system_administrator_required


@operations_manager_required
def manage_users(request):
    """Figure 3.7j: Manage User Accounts — list all staff and create new users."""
    if request.method == "POST":
        form = SystemUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            from core.audit import log_action

            log_action(
                request=request,
                action="user_modified",
                target_model="User",
                target_id=user.username,
                details=f"Created staff account '{user.username}' assigned to role '{user.role}'.",
            )

            messages.success(
                request,
                f"Account '{user.username}' created with role '{user.role}'.",
            )
            return redirect("accounts:manage_users")
    else:
        form = SystemUserCreationForm()

    users = User.objects.select_related("role").all().order_by("-date_joined")
    roles = Role.objects.all()
    return render(
        request,
        "accounts/manage_users.html",
        {"users": users, "form": form, "roles": roles},
    )


@system_administrator_required
def edit_user_role(request, user_id):
    """Update a user's role from the Manage Users screen."""
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        role_id = request.POST.get("role")
        if role_id:
            role = get_object_or_404(Role, pk=role_id)
            old_role = str(target_user.role)
            target_user.role = role
            target_user.save(update_fields=["role"])

            from core.audit import log_action

            log_action(
                request=request,
                action="user_modified",
                target_model="User",
                target_id=target_user.username,
                details=f"Modified role for user '{target_user.username}' from '{old_role}' to '{role}'.",
            )

            messages.success(
                request,
                f"'{target_user.username}' is now assigned the '{role}' role.",
            )
    return redirect("accounts:manage_users")


@system_administrator_required
def toggle_user_active(request, user_id):
    """Enable or disable a user account."""
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == "POST":
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=["is_active"])
        status = "activated" if target_user.is_active else "deactivated"

        from core.audit import log_action

        log_action(
            request=request,
            action="user_modified",
            target_model="User",
            target_id=target_user.username,
            details=f"Account status for '{target_user.username}' set to {status}.",
        )

        messages.success(request, f"'{target_user.username}' has been {status}.")

    return redirect("accounts:manage_users")
