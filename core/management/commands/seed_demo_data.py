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

        # 3. Create Realistic Enterprise & Aviation Customers
        realistic_customers = [
            # KQ Internal Departments
            ("KQ Inflight Catering Operations (Terminal 1A)", "catering.ops@kenya-airways.com | +254 20 6422000", "KQ Internal Department"),
            ("KQ Pride Centre Training Academy", "pridecentre.admin@kenya-airways.com | +254 20 6422800", "KQ Internal Department"),
            ("KQ Ground Services & Ramp Operations", "ramp.handling@kenya-airways.com | +254 20 6422310", "KQ Internal Department"),
            ("KQ Flight Operations (Terminal 1A Crew Lounge)", "flightops.crew@kenya-airways.com | +254 20 6422400", "KQ Internal Department"),
            ("KQ Technical Base Maintenance & Hangar", "techops.hangar@kenya-airways.com | +254 20 6422550", "KQ Internal Department"),
            ("KQ Cargo Freight Village (JKIA)", "cargo.logistics@kenya-airways.com | +254 20 6422600", "KQ Internal Department"),

            # Corporate Clients
            ("Safaricom PLC (HQ HQ1 & HQ2 Nairobi)", "procurement@safaricom.co.ke | +254 711 028000", "Corporate Client"),
            ("KCB Bank Kenya Ltd (Kencom Towers)", "facilities@kcbgroup.com | +254 20 3270000", "Corporate Client"),
            ("Equity Bank Group (Hospital Road Upper Hill)", "corporate.supplies@equitybank.co.ke | +254 763 063000", "Corporate Client"),
            ("Java House Africa Ltd (JKIA Airside Hub)", "supplychain@javahouseafrica.com | +254 709 174000", "Corporate Client"),
            ("Tradewinds Aviation Services (JKIA Station)", "ops@tradewinds-aviation.com | +254 722 203810", "Corporate Client"),
            ("Sarova Hotels & Resorts (Stanley & Panafric)", "procurement@sarovahotels.com | +254 709 111000", "Corporate Client"),
            ("Bolloré Transport & Logistics Kenya", "nbo.procurement@bollore.com | +254 20 6421000", "Corporate Client"),
            ("Swissport Kenya Cargo & Ground Handling", "nbo.stores@swissport.com | +254 20 6823000", "Corporate Client"),

            # Government Entities
            ("Kenya Civil Aviation Authority (KCAA)", "procurement@kcaa.or.ke | +254 20 6827470", "Government Entity"),
            ("Kenya Airports Authority (KAA Headquarters)", "info.supplies@kaa.go.ke | +254 20 6611000", "Government Entity"),
            ("Ministry of Transport & Infrastructure", "supplies@transport.go.ke | +254 20 2729200", "Government Entity"),
            ("Kenya Revenue Authority (KRA Customs JKIA)", "customs.jkia@kra.go.ke | +254 20 4999999", "Government Entity"),

            # Distributors
            ("Nairobi Bottlers Ltd (Industrial Area Depot)", "orders@nairobibottlers.co.ke | +254 20 6902000", "Distributor"),
            ("Chandarana Foodplus (Airport Junction)", "orders@foodplus.co.ke | +254 703 038000", "Distributor"),
            ("Quickmart Supermarket JKIA Distribution", "procurement@quickmart.co.ke | +254 700 800900", "Distributor"),
            ("Crown Beverages East Africa Ltd", "supply@crownbeverages.co.ke | +254 20 8645000", "Distributor"),
        ]
        customers = []
        for name, contact, acc_type in realistic_customers:
            c = Customer.objects.create(
                name=name,
                contact_info=contact,
                account_type=acc_type,
            )
            customers.append(c)

        # 4. Create Orders
        now = timezone.now()
        statuses = [Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.FULFILLED, Order.Status.INVOICED]
        vans = ["KQ Van KBZ 482Y", "KQ Logistics Van KCG 119Q", "Aviation Ramp Truck KDA 702P", "Airside Dispatch Van KBN 553T"]
        drivers = ["Driver J. Kamau", "Driver P. Ochieng", "Driver M. Mutua", "Driver D. Kiprop", "Driver E. Waweru"]

        invoices_created = 0
        payments_created = 0

        for _ in range(250):
            customer = random.choice(customers)
            days_ago = random.randint(0, 365)
            order_date = now - timedelta(days=days_ago)

            order_status = random.choice(statuses)
            dispatch_notes = ""
            if order_status in [Order.Status.FULFILLED, Order.Status.INVOICED]:
                gate_pass = random.randint(1000, 9999)
                dispatch_notes = f"{random.choice(vans)} | {random.choice(drivers)} | Gate Pass #{gate_pass}"

            order = Order.objects.create(
                customer=customer,
                status=order_status,
                fulfillment_notes=dispatch_notes,
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
                Invoice.objects.filter(pk=invoice.pk).update(issue_date=order_date.date())
                invoices_created += 1

                # Select payment method based on customer type
                if customer.account_type == "KQ Internal Department":
                    p_method = Payment.Method.INTERNAL_JOURNAL
                    ref_code = f"JRNL-KQ-{random.randint(10000, 99999)}"
                elif customer.account_type == "Corporate Client":
                    p_method = random.choice([Payment.Method.BANK_TRANSFER, Payment.Method.MPESA, Payment.Method.CHEQUE])
                    ref_code = f"EFT-{random.choice(['KCB', 'EQT', 'SCB'])}-{random.randint(10000, 99999)}"
                elif customer.account_type == "Distributor":
                    p_method = random.choice([Payment.Method.MPESA, Payment.Method.BANK_TRANSFER, Payment.Method.CASH])
                    ref_code = f"MPESA-Q{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{random.randint(10000, 99999)}"
                else:  # Government Entity
                    p_method = random.choice([Payment.Method.BANK_TRANSFER, Payment.Method.CHEQUE])
                    ref_code = f"TREASURY-CHQ-{random.randint(10000, 99999)}"

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
                        reference=ref_code,
                        notes="Settled in full per contract"
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
                        reference=f"{ref_code}-PART",
                        notes="Partial installment"
                    )
                    payments_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded demo data: 250 orders, {invoices_created} invoices, {payments_created} payments.'
        ))
