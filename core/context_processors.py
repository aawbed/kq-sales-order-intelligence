def notifications(request):
    """
    Supplies the in-app notification count and recent alerts to all templates.
    """
    if not request.user.is_authenticated:
        return {
            "unread_notifications_count": 0,
            "recent_notifications": [],
        }

    from core.models import Notification

    user_notifs = Notification.objects.filter(recipient=request.user)
    unread_count = user_notifs.filter(is_read=False).count()
    recent = user_notifs.order_by("-created_at")[:6]

    return {
        "unread_notifications_count": unread_count,
        "recent_notifications": recent,
    }
