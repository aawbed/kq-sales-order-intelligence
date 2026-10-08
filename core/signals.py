from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from core.audit import log_action
from core.models import AuditLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    role_name = getattr(user.role, "role_name", "No Role")
    log_action(
        user=user,
        action=AuditLog.Action.LOGIN,
        target_model="User",
        target_id=user.username,
        details=f"User '{user.username}' successfully authenticated (Role: {role_name}).",
        request=request,
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user and getattr(user, "is_authenticated", False):
        log_action(
            user=user,
            action=AuditLog.Action.LOGOUT,
            target_model="User",
            target_id=user.username,
            details=f"User '{user.username}' signed out.",
            request=request,
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get("username", "<unknown>")
    log_action(
        user=None,
        action=AuditLog.Action.FAILED_LOGIN,
        target_model="User",
        target_id=username,
        details=f"Failed login attempt for username '{username}'.",
        request=request,
    )
