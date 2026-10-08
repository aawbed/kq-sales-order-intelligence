from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Role
from inventory.models import Product, Stock
from orders.models import Customer, Invoice, Order, OrderItem, Payment

User = get_user_model()


class OrdersAndFinancialTests(TestCase):
    def setUp(self):
        self.role_sales = Role.objects.create(role_name=Role.RoleName.SALES_AGENT)
        self.user = User.objects.create_user(
            username="sales_agent_test",
            password="Password123!",
            role=self.role_sales,
        )

        self.customer = Customer.objects.create(
            name="KQ Inflight Catering",
            contact_info="catering@kenya-airways.com",
            account_type="KQ Internal Department",
        )

        self.product_500ml = Product.objects.create(
            name="500ml Bottle Case (24 Pack)",
            unit_price=Decimal("650.00"),
        )
        self.product_20l = Product.objects.create(
            name="20L Dispenser Bottle",
            unit_price=Decimal("450.00"),
        )

        Stock.objects.create(
            product=self.product_500ml,
            quantity_on_hand=500,
            reorder_level=100,
        )
        Stock.objects.create(
            product=self.product_20l,
            quantity_on_hand=200,
            reorder_level=50,
        )

    def test_customer_creation_and_history(self):
        self.assertEqual(str(self.customer), "KQ Inflight Catering")
        self.assertEqual(self.customer.account_type, "KQ Internal Department")
        self.assertEqual(self.customer.view_order_history().count(), 0)

    def test_order_lifecycle_and_line_calculation(self):
        # 1. Create order
        order = Order.objects.create(
            customer=self.customer,
            created_by=self.user,
            priority=Order.Priority.URGENT,
        )
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.priority, Order.Priority.URGENT)

        # 2. Add line items
        item1 = order.add_item(self.product_500ml, quantity=10, unit_price=Decimal("650.00"))
        item2 = order.add_item(self.product_20l, quantity=5, unit_price=Decimal("450.00"))

        self.assertEqual(item1.line_total, Decimal("6500.00"))
        self.assertEqual(item2.line_total, Decimal("2250.00"))

        subtotal = sum(i.line_total for i in order.items.all())
        self.assertEqual(subtotal, Decimal("8750.00"))

        # 3. Status progression
        order.update_status(Order.Status.CONFIRMED)
        self.assertEqual(order.status, Order.Status.CONFIRMED)

        order.update_status(Order.Status.FULFILLED)
        self.assertEqual(order.status, Order.Status.FULFILLED)

    def test_invoice_generation_vat_and_payments(self):
        order = Order.objects.create(customer=self.customer, created_by=self.user)
        order.add_item(self.product_500ml, quantity=100, unit_price=Decimal("650.00"))

        # Expected subtotal: 100 * 650 = 65,000.00
        # Expected 16% VAT: 65,000 * 0.16 = 10,400.00
        # Expected total: 75,400.00
        invoice = Invoice.generate(order)

        self.assertEqual(order.status, Order.Status.INVOICED)
        self.assertEqual(invoice.subtotal, Decimal("65000.00"))
        self.assertEqual(invoice.vat_amount, Decimal("10400.00"))
        self.assertEqual(invoice.total_amount, Decimal("75400.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.UNPAID)
        self.assertEqual(invoice.balance, Decimal("75400.00"))

        # Partial Payment via M-Pesa
        payment1 = Payment.objects.create(
            invoice=invoice,
            amount=Decimal("35400.00"),
            method=Payment.Method.MPESA,
            reference="QKH7892341",
            recorded_by=self.user,
        )
        self.assertEqual(invoice.amount_paid, Decimal("35400.00"))
        self.assertEqual(invoice.balance, Decimal("40000.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIALLY_PAID)

        # Final Payment via Bank Transfer
        payment2 = Payment.objects.create(
            invoice=invoice,
            amount=Decimal("40000.00"),
            method=Payment.Method.BANK_TRANSFER,
            reference="EFT-KQ-99812",
            recorded_by=self.user,
        )
        self.assertEqual(invoice.amount_paid, Decimal("75400.00"))
        self.assertEqual(invoice.balance, Decimal("0.00"))
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PAID)
