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


class LoginAttempt(models.Model):
    """
    Authentication Module: Tracks failed authentication attempts per username
    and client IP to enforce account lockout after 5 consecutive failed attempts.
    """

    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.CharField(max_length=50, blank=True, default="", db_index=True)
    failed_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_attempt = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["username", "ip_address"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.ip_address}): {self.failed_count} failures"

    @classmethod
    def get_record(cls, username, ip_address=""):
        clean_user = (username or "").lower().strip()
        record, _ = cls.objects.get_or_create(
            username=clean_user,
            ip_address=ip_address or "",
        )
        return record

    def is_locked(self):
        from django.utils import timezone

        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def remaining_lockout_seconds(self):
        from django.utils import timezone

        if self.locked_until and self.locked_until > timezone.now():
            return int((self.locked_until - timezone.now()).total_seconds())
        return 0

    def record_failure(self, request=None):
        from datetime import timedelta
        from django.utils import timezone
        from core.audit import log_action

        self.failed_count += 1
        if self.failed_count >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=15)
            log_action(
                action="account_lockout",
                target_model="User",
                target_id=self.username,
                details=f"Account '{self.username}' temporarily locked out for 15 minutes after 5 consecutive failed login attempts.",
                request=request,
            )
        self.save()
        return self.failed_count

    def reset_failures(self):
        if self.failed_count > 0 or self.locked_until is not None:
            self.failed_count = 0
            self.locked_until = None
            self.save(update_fields=["failed_count", "locked_until"])


