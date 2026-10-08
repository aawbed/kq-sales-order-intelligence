"""
End-to-End Order-to-Cash Integration Test Suite.

Validates the complete lifecycle:
Order Creation (Sales Agent) -> Order Confirmation -> Fulfilment & Stock Deduction (Warehouse Officer)
-> Invoice Generation with 16% VAT -> Partial Payment (M-Pesa) -> Final Payment (Bank Transfer)
-> Accounts Receivable Settlement -> Security Audit Logging & Alerts.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Role
from core.models import AuditLog, Notification
from inventory.models import Product, Stock
from orders.models import Customer, Invoice, Order, OrderItem, Payment

User = get_user_model()


class OrderToCashIntegrationTests(TestCase):
    def setUp(self):
        # 1. User roles
        self.role_sales = Role.objects.create(role_name=Role.RoleName.SALES_AGENT)
        self.role_wh = Role.objects.create(role_name=Role.RoleName.WAREHOUSE_OFFICER)
        self.role_ops = Role.objects.create(role_name=Role.RoleName.OPERATIONS_MANAGER)

        # 2. Actors
        self.sales_agent = User.objects.create_user(
            username="agent_kamau",
            password="Password123!",
            role=self.role_sales,
        )
        self.warehouse_officer = User.objects.create_user(
            username="officer_otieno",
            password="Password123!",
            role=self.role_wh,
        )
        self.ops_manager = User.objects.create_user(
            username="manager_wanjiku",
            password="Password123!",
            role=self.role_ops,
        )

        # 3. Customer & Inventory
        self.customer = Customer.objects.create(
            name="KQ Pride Lounge Catering",
            contact_info="pride.lounge@kenya-airways.com",
            account_type="KQ Internal Department",
        )

        self.water_500ml = Product.objects.create(
            name="500ml Bottle Case (24 Pack)",
            unit_price=Decimal("600.00"),
        )
        self.stock = Stock.objects.create(
            product=self.water_500ml,
            quantity_on_hand=1000,
            reorder_level=200,
        )

        self.client = Client()

    def test_complete_order_to_cash_lifecycle(self):
        """
        Tests the continuous business flow through all four roles and financial records.
        """
        # =====================================================================
        # Step 1: Sales Agent places order
        # =====================================================================
        self.client.force_login(self.sales_agent)
        order = Order.objects.create(
            customer=self.customer,
            created_by=self.sales_agent,
            priority=Order.Priority.URGENT,
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            order=order,
            product=self.water_500ml,
            quantity=300,
            unit_price=Decimal("600.00"),
        )

        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.priority, Order.Priority.URGENT)
        self.assertEqual(self.stock.quantity_on_hand, 1000)  # Stock untouched while pending

        # =====================================================================
        # Step 2: Order is confirmed
        # =====================================================================
        order.update_status(Order.Status.CONFIRMED)
        self.assertEqual(order.status, Order.Status.CONFIRMED)

        # Confirm it appears in Warehouse Officer's fulfilment queue
        self.client.force_login(self.warehouse_officer)
        fulfilment_resp = self.client.get(reverse("inventory:confirm_fulfilment"))
        self.assertEqual(fulfilment_resp.status_code, 200)
        self.assertContains(fulfilment_resp, f"KQ-{order.order_id}")

        # =====================================================================
        # Step 3: Warehouse Officer fulfils order -> Stock is deducted
        # =====================================================================
        confirm_url = reverse("inventory:confirm_order", kwargs={"order_id": order.order_id})
        post_resp = self.client.post(confirm_url, follow=True)
        self.assertEqual(post_resp.status_code, 200)

        order.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(order.status, Order.Status.FULFILLED)
        # 1000 initial - 300 ordered = 700 units remaining
        self.assertEqual(self.stock.quantity_on_hand, 700)

        # Verify audit trail for fulfilment
        audit_log = AuditLog.objects.filter(
            action="order_status_changed",
            target_id=f"KQ-{order.order_id}",
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertIn("Fulfilled", audit_log.details)

        # =====================================================================
        # Step 4: Invoice Generation (16% VAT applied)
        # =====================================================================
        # Subtotal: 300 * 600 = 180,000.00
        # 16% VAT: 180,000 * 0.16 = 28,800.00
        # Total: 208,800.00
        invoice = Invoice.generate(order)
        order.refresh_from_db()

        self.assertEqual(order.status, Order.Status.INVOICED)
        self.assertEqual(invoice.subtotal, Decimal("180000.00"))
        self.assertEqual(invoice.vat_amount, Decimal("28800.00"))
        self.assertEqual(invoice.total_amount, Decimal("208800.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.UNPAID)
        self.assertEqual(invoice.balance, Decimal("208800.00"))

        # =====================================================================
        # Step 5: Customer Payment Phase 1 (Partial Payment via M-Pesa)
        # =====================================================================
        self.client.force_login(self.ops_manager)
        payment_url = reverse("orders:record_payment", kwargs={"order_id": order.order_id})

        pay_data_1 = {
            "amount": "108800.00",
            "method": Payment.Method.MPESA,
            "reference": "MPESA-KQ-10023",
            "notes": "First installment via M-Pesa Paybill",
        }
        pay_resp_1 = self.client.post(payment_url, pay_data_1, follow=True)
        self.assertEqual(pay_resp_1.status_code, 200)

        self.assertEqual(invoice.amount_paid, Decimal("108800.00"))
        self.assertEqual(invoice.balance, Decimal("100000.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIALLY_PAID)

        # Verify payment audit log
        pay_audit = AuditLog.objects.filter(action=AuditLog.Action.PAYMENT_RECORDED).first()
        self.assertIsNotNone(pay_audit)
        self.assertIn("108,800.00", pay_audit.details)

        # =====================================================================
        # Step 6: Customer Payment Phase 2 (Final Settlement via Bank Transfer)
        # =====================================================================
        pay_data_2 = {
            "amount": "100000.00",
            "method": Payment.Method.BANK_TRANSFER,
            "reference": "EFT-KQ-CBK-4410",
            "notes": "Final settlement balance",
        }
        pay_resp_2 = self.client.post(payment_url, pay_data_2, follow=True)
        self.assertEqual(pay_resp_2.status_code, 200)

        self.assertEqual(invoice.amount_paid, Decimal("208800.00"))
        self.assertEqual(invoice.balance, Decimal("0.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PAID)

        # Accounts Receivable Check
        ar_resp = self.client.get(reverse("analytics:accounts_receivable"))
        self.assertEqual(ar_resp.status_code, 200)

        # =====================================================================
        # Step 7: Inventory Low Stock Reorder Threshold Alert
        # =====================================================================
        # Deduct further 600 units (700 -> 100), crossing reorder level (200)
        self.stock.update_level(-600, reason="High volume flight catering run")
        self.assertEqual(self.stock.quantity_on_hand, 100)
        self.assertTrue(self.stock.is_low)

        # Check automated notification delivered
        alert = Notification.objects.filter(
            category=Notification.Category.LOW_STOCK,
            recipient=self.warehouse_officer,
        ).first()
        self.assertIsNotNone(alert)
        self.assertIn("Low Stock Alert", alert.title)
        self.assertIn("500ml Bottle Case", alert.message)
