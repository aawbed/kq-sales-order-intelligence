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
