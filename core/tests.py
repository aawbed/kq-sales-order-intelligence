from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from accounts.models import Role
from core.audit import log_action
from core.models import AuditLog, Notification

User = get_user_model()


class CoreAuditAndNotificationTests(TestCase):
    def setUp(self):
        self.role_admin = Role.objects.create(role_name=Role.RoleName.SYSTEM_ADMINISTRATOR)
        self.user = User.objects.create_user(
            username="audit_test_admin",
            password="Password123!",
            role=self.role_admin,
        )
        self.factory = RequestFactory()

    def test_log_action_creates_immutable_audit_entry(self):
        req = self.factory.get("/")
        req.user = self.user

        log = log_action(
            user=self.user,
            action=AuditLog.Action.ORDER_CREATED,
            target_model="Order",
            target_id="101",
            details="Created high priority order for VIP client.",
            request=req,
        )

        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, AuditLog.Action.ORDER_CREATED)
        self.assertEqual(log.target_model, "Order")
        self.assertEqual(log.target_id, "101")
        self.assertIn("Created high priority order", log.details)
        self.assertIn("User Login" if log.action == "login" else "Order Created", str(log))

    def test_notification_delivery_and_read_status(self):
        count = Notification.notify_role(
            role_name=Role.RoleName.SYSTEM_ADMINISTRATOR,
            title="System Alert Test",
            message="Database maintenance scheduled.",
            category=Notification.Category.SYSTEM,
            level=Notification.Level.INFO,
        )
        self.assertEqual(count, 1)

        note = Notification.objects.filter(recipient=self.user).first()
        self.assertIsNotNone(note)
        self.assertFalse(note.is_read)

        # Mark as read
        note.mark_as_read()
        self.assertTrue(note.is_read)
