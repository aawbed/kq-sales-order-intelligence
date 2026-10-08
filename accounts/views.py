from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import SystemUserCreationForm
from accounts.models import Role, User
from core.audit import get_client_ip
from core.models import LoginAttempt
from core.permissions import operations_manager_required, system_administrator_required


class CustomLoginView(auth_views.LoginView):
    """
    Figure 3.7a: Staff Authentication with Login Attempt Limiting (5 attempts / 15-min lockout).
    """

    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            username = request.POST.get("username", "").strip().lower()
            ip = get_client_ip(request)
            attempt = LoginAttempt.get_record(username, ip)
            if attempt.is_locked():
                mins = max(1, (attempt.remaining_lockout_seconds() + 59) // 60)
                lockout_msg = (
                    f"Account security lockout: Too many consecutive failed attempts. "
                    f"Account is locked. Please try again in {mins} minute(s)."
                )
                form = self.get_form()
                return self.render_to_response(
                    self.get_context_data(
                        form=form,
                        lockout_message=lockout_msg,
                        is_locked=True,
                    )
                )
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "").strip().lower()
        ip = get_client_ip(self.request)
        attempt = LoginAttempt.get_record(username, ip)
        count = attempt.record_failure(request=self.request)

        if attempt.is_locked():
            lockout_msg = (
                "Security Alert: Maximum allowed failed login attempts (5) exceeded. "
                "This account is temporarily locked for 15 minutes."
            )
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    lockout_message=lockout_msg,
                    is_locked=True,
                )
            )
        else:
            remaining = 5 - count
            warning = f"Invalid credentials. You have {remaining} attempt(s) remaining before temporary account lockout."
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    attempt_warning=warning,
                )
            )

    def form_valid(self, form):
        username = self.request.POST.get("username", "").strip().lower()
        ip = get_client_ip(self.request)
        attempt = LoginAttempt.get_record(username, ip)
        attempt.reset_failures()
        return super().form_valid(form)


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
