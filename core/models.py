from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    In-app alert notification centre.
    Corresponds to automated alerts for low stock and ML anomalies per Section 3.3.
    """

    class Category(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock Alert"
        ANOMALY = "anomaly", "ML Anomaly Detected"
        ORDER = "order", "Order Update"
        SYSTEM = "system", "System Notice"

    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        DANGER = "danger", "Critical"

    notification_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.SYSTEM,
    )
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.INFO,
    )
    link = models.CharField(max_length=255, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"[{self.get_level_display()}] {self.title} ({self.recipient.username})"

    @classmethod
    def notify_role(cls, role_name, title, message, category, level, link=""):
        """Dispatches an alert to all active users with the given role."""
        from accounts.models import User
        users = User.objects.filter(role__role_name=role_name, is_active=True)
        notifications = [
            cls(
                recipient=user,
                title=title,
                message=message,
                category=category,
                level=level,
                link=link,
            )
            for user in users
        ]
        if notifications:
            cls.objects.bulk_create(notifications)
        return len(notifications)


class AuditLog(models.Model):
    """
    Corresponds to the audit trail requirement in the Authentication Module:
    records all user actions, including order creation, status changes, stock updates,
    payments, user management, and login activity.
    """

    class Action(models.TextChoices):
        LOGIN = "login", "User Login"
        LOGOUT = "logout", "User Logout"
        FAILED_LOGIN = "failed_login", "Failed Login Attempt"
        ACCOUNT_LOCKOUT = "account_lockout", "Account Lockout"
        ORDER_CREATED = "order_created", "Order Created"
        ORDER_STATUS_CHANGED = "order_status_changed", "Order Status Updated"
        STOCK_ADJUSTED = "stock_adjusted", "Stock Level Adjusted"
        PAYMENT_RECORDED = "payment_recorded", "Payment Recorded"
        SETTINGS_UPDATED = "settings_updated", "System Settings Updated"
        USER_MODIFIED = "user_modified", "User Account Modified"

    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    target_model = models.CharField(max_length=50, blank=True, default="")
    target_id = models.CharField(max_length=50, blank=True, default="")
    details = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log Entry"
        verbose_name_plural = "Audit Log Entries"

    def __str__(self):
        actor = self.user.username if self.user else "Anonymous"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {actor} - {self.get_action_display()}"

