import os
import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from orders.models import Customer, Order, OrderItem, Invoice, Payment
from inventory.models import Product, Stock
from accounts.models import Role, User


class Command(BaseCommand):
    help = 'Seeds the database with demo data for operations, invoices, payments, and ML models'

    def handle(self, *args, **kwargs):
        # 0. Ensure Roles and Demo Accounts
        roles = {}
        for role_name, _ in Role.RoleName.choices:
            r, _ = Role.objects.get_or_create(role_name=role_name)
            roles[role_name] = r

        demo_users = [
            ("admin", "admin@kq.co.ke", "system_administrator", True, True),
            ("operations", "operations@kq.co.ke", "operations_manager", False, False),
            ("sales", "sales@kq.co.ke", "sales_agent", False, False),
            ("warehouse", "warehouse@kq.co.ke", "warehouse_officer", False, False),
        ]
        for uname, email, r_name, is_staff, is_super in demo_users:
            u, _ = User.objects.get_or_create(username=uname, defaults={"email": email})
            u.set_password("Password123!")
            u.role = roles[r_name]
            u.is_staff = is_staff
            u.is_superuser = is_super
            u.save()

        # 1. Clear existing transactional data
        Payment.objects.all().delete()
        Invoice.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Stock.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()
        
        # 2. Create Products & Stock
        product_names = [
            ("500ml Bottle Case (24 Pack)", 1200.00),
            ("1L Bottle Case (12 Pack)", 1800.00),
            ("5L Jerrycan", 350.00),
            ("20L Dispenser Bottle", 1800.00),
            ("250ml Cups Case (48 Pack)", 960.00),
            ("Premium Glass 500ml (12 Pack)", 3600.00),
            ("Flavored Water 500ml Case (24 Pack)", 1440.00),
            ("10L Bulk Dispenser Box", 900.00),
        ]
        products = []
        for name, price in product_names:
            p = Product.objects.create(name=name, unit_price=price)
            Stock.objects.create(product=p, quantity_on_hand=random.randint(100, 1000), reorder_level=50)
            products.append(p)

        # 3. Create Customers
        account_types = ["KQ Internal Department", "Corporate Client", "Government Entity", "Distributor"]
        customers = []
        for i in range(15):
            c = Customer.objects.create(
                name=f"Customer {i+1}",
                contact_info=f"contact{i+1}@example.com",
                account_type=random.choice(account_types)
            )
            customers.append(c)
            
        # 4. Create Orders
        now = timezone.now()
        statuses = [Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.FULFILLED, Order.Status.INVOICED]
        
        invoices_created = 0
        payments_created = 0

        for _ in range(250):
            customer = random.choice(customers)
            # Random date within last 365 days
            days_ago = random.randint(0, 365)
            order_date = now - timedelta(days=days_ago)
            
            order_status = random.choice(statuses)
            order = Order.objects.create(
                customer=customer,
                status=order_status
            )
            # Update order_date (auto_now_add overrides on create)
            Order.objects.filter(pk=order.pk).update(order_date=order_date)
            
            # Add items
            order_subtotal = Decimal("0.00")
            for _ in range(random.randint(1, 5)):
                product = random.choice(products)
                quantity = random.randint(1, 50)
                if random.random() < 0.05:
                    quantity = random.randint(200, 500)  # Anomalous quantity
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.unit_price
                )
                order_subtotal += Decimal(str(item.line_total))

            # 5. Create Invoices and Payments for INVOICED orders
            if order_status == Order.Status.INVOICED:
                vat = round(order_subtotal * Decimal("0.16"), 2)
                total_invoiced = order_subtotal + vat
                invoice = Invoice.objects.create(
                    order=order,
                    total_amount=total_invoiced
                )
                # Ensure issue date matches historical order date
                Invoice.objects.filter(pk=invoice.pk).update(issue_date=order_date.date())
                invoices_created += 1

                # Select payment method based on customer type
                if customer.account_type == "KQ Internal Department":
                    p_method = Payment.Method.INTERNAL_JOURNAL
                    ref_prefix = "JRNL"
                elif customer.account_type == "Corporate Client":
                    p_method = random.choice([Payment.Method.BANK_TRANSFER, Payment.Method.MPESA, Payment.Method.CHEQUE])
                    ref_prefix = "CORP"
                elif customer.account_type == "Distributor":
                    p_method = random.choice([Payment.Method.MPESA, Payment.Method.BANK_TRANSFER, Payment.Method.CASH])
                    ref_prefix = "DST"
                else:  # Government Entity
                    p_method = random.choice([Payment.Method.BANK_TRANSFER, Payment.Method.CHEQUE])
                    ref_prefix = "GOV"

                # 60% Paid, 25% Partially Paid, 15% Unpaid
                roll = random.random()
                if roll < 0.60:
                    # Fully Paid
                    pay_date = (order_date + timedelta(days=random.randint(1, 15))).date()
                    if pay_date > now.date():
                        pay_date = now.date()
                    Payment.objects.create(
                        invoice=invoice,
                        amount=total_invoiced,
                        payment_date=pay_date,
                        method=p_method,
                        reference=f"{ref_prefix}-{random.randint(10000, 99999)}",
                        notes="Settled in full"
                    )
                    payments_created += 1
                elif roll < 0.85:
                    # Partially Paid (e.g. 50% deposit)
                    partial_amount = round(total_invoiced * Decimal(str(random.uniform(0.3, 0.7))), 2)
                    pay_date = (order_date + timedelta(days=random.randint(1, 10))).date()
                    if pay_date > now.date():
                        pay_date = now.date()
                    Payment.objects.create(
                        invoice=invoice,
                        amount=partial_amount,
                        payment_date=pay_date,
                        method=p_method,
                        reference=f"{ref_prefix}-PART-{random.randint(1000, 9999)}",
                        notes="Partial installment"
                    )
                    payments_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded demo data: 250 orders, {invoices_created} invoices, {payments_created} payments.'
        ))
