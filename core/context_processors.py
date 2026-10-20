def notifications(request):
    """
    Supplies the in-app notification count, recent alerts, and demo switcher visibility to all templates.
    """
    if not request.user.is_authenticated:
        return {
            "unread_notifications_count": 0,
            "recent_notifications": [],
            "can_switch_demo_role": False,
        }

    from django.conf import settings
    from accounts.models import Role
    from core.models import Notification

    user_notifs = Notification.objects.filter(recipient=request.user)
    unread_count = user_notifs.filter(is_read=False).count()
    recent = user_notifs.order_by("-created_at")[:6]

    demo_enabled = getattr(settings, "DEMO_MODE", settings.DEBUG)
    is_admin_user = bool(
        getattr(request.user, "is_superuser", False)
        or (
            getattr(request.user, "role", None) is not None
            and request.user.role.role_name == Role.RoleName.SYSTEM_ADMINISTRATOR
        )
    )
    can_switch = bool(demo_enabled and (is_admin_user or request.session.get("demo_presenter", False)))

    return {
        "unread_notifications_count": unread_count,
        "recent_notifications": recent,
        "can_switch_demo_role": can_switch,
    }
