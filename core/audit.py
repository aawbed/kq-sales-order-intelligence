import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Safely extracts the client IP address from the request object."""
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def log_action(user=None, action="", target_model="", target_id="", details="", request=None):
    """
    Records an immutable audit trail entry.
    Can be called directly or with a request object to automatically infer user and client IP.
    """
    from core.models import AuditLog

    ip = None
    if request:
        if user is None and getattr(request, "user", None) and request.user.is_authenticated:
            user = request.user
        ip = get_client_ip(request)

    actual_user = user if getattr(user, "is_authenticated", False) else None

    try:
        return AuditLog.objects.create(
            user=actual_user,
            action=action,
            target_model=target_model,
            target_id=str(target_id),
            details=details,
            ip_address=ip,
        )
    except Exception as exc:
        logger.warning("Failed to record audit log: %s", exc)
        return None
