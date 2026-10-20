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

    def test_demo_role_switcher_blocks_unauthorized_escalation(self):
        from django.urls import reverse

        role_sales = Role.objects.create(role_name=Role.RoleName.SALES_AGENT)
        User.objects.create_user(username="admin", password="Password123!", role=self.role_admin, is_superuser=True)
        User.objects.create_user(username="sales", password="Password123!", role=role_sales)

        # Direct non-admin login must receive 403 when attempting to switch to admin
        self.client.login(username="sales", password="Password123!")
        resp = self.client.get(reverse("core:switch_demo_role", args=["admin"]))
        self.assertEqual(resp.status_code, 403)

    def test_mark_notification_read_blocks_external_open_redirect(self):
        from django.urls import reverse

        note = Notification.objects.create(
            recipient=self.user,
            title="Test",
            message="Body",
            category=Notification.Category.SYSTEM,
        )
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("core:mark_notification_read", args=[note.notification_id])
            + "?next=https://evil.example.com/phish"
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("core:notification_list"))

    def test_mark_all_read_requires_post(self):
        from django.urls import reverse

        self.client.force_login(self.user)
        get_resp = self.client.get(reverse("core:mark_all_read"))
        self.assertEqual(get_resp.status_code, 405)
        post_resp = self.client.post(reverse("core:mark_all_read"))
        self.assertEqual(post_resp.status_code, 302)

