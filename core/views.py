from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Notification


@login_required
def role_home_redirect(request):
    """
    Smart landing page — redirects each user to their role-appropriate
    home screen instead of throwing a 403 on the wrong page.
    """
    role = getattr(request.user, "role", None)
    if role is None:
        # No role assigned — send to admin to get one assigned
        return render(request, "core/no_role.html")

    role_name = role.role_name

    if role_name == "sales_agent":
        return redirect("orders:track_orders")
    elif role_name == "warehouse_officer":
        return redirect("inventory:confirm_fulfilment")
    elif role_name == "operations_manager":
        return redirect("analytics:dashboard")
    elif role_name == "system_administrator":
        return redirect("analytics:system_settings")

    return redirect("accounts:login")


def custom_permission_denied(request, exception=None):
    """
    Friendly 403 page with a button to go back to the correct home page.
    """
    return render(request, "core/403.html", status=403)


@login_required
def notification_list(request):
    """
    In-App Notification Centre:
    Displays historical and active alerts for the current user.
    """
    status_filter = request.GET.get("status", "all")
    category_filter = request.GET.get("category", "")

    notifs = Notification.objects.filter(recipient=request.user)

    if status_filter == "unread":
        notifs = notifs.filter(is_read=False)
    elif status_filter == "read":
        notifs = notifs.filter(is_read=True)

    if category_filter:
        notifs = notifs.filter(category=category_filter)

    paginator = Paginator(notifs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    context = {
        "page_obj": page_obj,
        "unread_count": unread_count,
        "status_filter": status_filter,
        "category_filter": category_filter,
    }
    return render(request, "core/notifications.html", context)


@login_required
def mark_notification_read(request, notification_id):
    """
    Marks an individual notification as read and directs the user to the target resource.
    """
    notif = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=["is_read"])

    # If notification has a link, redirect there, else back to list
    next_url = request.GET.get("next") or notif.link or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("core:notification_list")


@login_required
def mark_all_read(request):
    """
    Marks all unread notifications for current user as read.
    """
    count = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    if count > 0:
        messages.success(request, f"Marked {count} notification(s) as read.")
    next_url = request.META.get("HTTP_REFERER") or "core:notification_list"
    return redirect(next_url)
