from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.models import Role
from core.models import LoginAttempt
from core.permissions import (
    operations_manager_required,
    operations_or_admin_required,
    role_required,
    sales_agent_required,
    system_administrator_required,
    warehouse_officer_required,
)

User = get_user_model()


class AccountsAndSecurityTests(TestCase):
    def setUp(self):
        self.role_sales = Role.objects.create(
            role_name=Role.RoleName.SALES_AGENT,
        )
        self.role_op = Role.objects.create(
            role_name=Role.RoleName.OPERATIONS_MANAGER,
        )
        self.role_admin = Role.objects.create(
            role_name=Role.RoleName.SYSTEM_ADMINISTRATOR,
        )
        self.role_wh = Role.objects.create(
            role_name=Role.RoleName.WAREHOUSE_OFFICER,
        )

        self.user_sales = User.objects.create_user(
            username="sales1",
            password="Password123!",
            role=self.role_sales,
        )
        self.user_op = User.objects.create_user(
            username="ops1",
            password="Password123!",
            role=self.role_op,
        )
        self.user_admin = User.objects.create_user(
            username="admin1",
            password="Password123!",
            role=self.role_admin,
        )

        self.factory = RequestFactory()

    def test_role_assignment_and_string_representation(self):
        self.assertEqual(self.user_sales.role.role_name, Role.RoleName.SALES_AGENT)
        self.assertIn("Sales Agent", str(self.role_sales))

    def test_brute_force_lockout_logic(self):
        record = LoginAttempt.get_record(username="target_user", ip_address="127.0.0.1")

        # 1-4 failures should not lock
        for i in range(1, 5):
            count = record.record_failure()
            self.assertEqual(count, i)
            self.assertFalse(record.is_locked())

        # 5th failure should trigger lockout
        count = record.record_failure()
        self.assertEqual(count, 5)
        self.assertTrue(record.is_locked())
        self.assertGreater(record.remaining_lockout_seconds(), 0)

        # Successful login resets the attempt counter
        record.reset_failures()
        self.assertEqual(record.failed_count, 0)
        self.assertFalse(record.is_locked())

    def test_role_permission_decorators(self):
        @sales_agent_required
        def sales_view(request):
            return "sales_ok"

        @operations_manager_required
        def ops_view(request):
            return "ops_ok"

        @system_administrator_required
        def admin_view(request):
            return "admin_ok"

        @operations_or_admin_required
        def shared_view(request):
            return "shared_ok"

        req = self.factory.get("/")

        # Sales user access
        req.user = self.user_sales
        self.assertEqual(sales_view(req), "sales_ok")
        with self.assertRaises(PermissionDenied):
            ops_view(req)
        with self.assertRaises(PermissionDenied):
            admin_view(req)
        with self.assertRaises(PermissionDenied):
            shared_view(req)

        # Operations Manager access
        req.user = self.user_op
        self.assertEqual(ops_view(req), "ops_ok")
        self.assertEqual(shared_view(req), "shared_ok")
        with self.assertRaises(PermissionDenied):
            sales_view(req)

        # System Administrator access
        req.user = self.user_admin
        self.assertEqual(admin_view(req), "admin_ok")
        self.assertEqual(shared_view(req), "shared_ok")
        with self.assertRaises(PermissionDenied):
            sales_view(req)
