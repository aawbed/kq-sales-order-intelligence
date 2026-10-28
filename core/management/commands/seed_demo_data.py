import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Role, User
from analytics.models import MLModelRun
from inventory.models import Product, Stock
from orders.models import Customer, Invoice, Order, OrderItem, Payment


class Command(BaseCommand):
    help = "Seeds the database with demo data for operations, invoices, payments, and ML models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force seeding and wiping existing data even when DEBUG is False.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options.get("force"):
            raise CommandError(
                "Refusing to wipe and seed demo data when DEBUG=False. "
                "Pass --force if you explicitly intend to reset this environment."
            )

        rng = random.Random(42)

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

        # 1. Clear existing transactional & ML run data
        Payment.objects.all().delete()
        Invoice.objects.all().delete()
        OrderItem.objects.all().delete()
        MLModelRun.objects.all().delete()
        Order.objects.all().delete()
        Stock.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()

        # 2. Create Products & Stock
        product_names = [
            ("500ml Bottle Case (24 Pack)", Decimal("1200.00")),
            ("1L Bottle Case (12 Pack)", Decimal("1800.00")),
            ("5L Jerrycan", Decimal("350.00")),
            ("20L Dispenser Bottle", Decimal("1800.00")),
            ("250ml Cups Case (48 Pack)", Decimal("960.00")),
            ("Premium Glass 500ml (12 Pack)", Decimal("3600.00")),
            ("Flavored Water 500ml Case (24 Pack)", Decimal("1440.00")),
            ("10L Bulk Dispenser Box", Decimal("900.00")),
        ]
        products = []
        for name, price in product_names:
            p = Product.objects.create(name=name, unit_price=price)
            Stock.objects.create(product=p, quantity_on_hand=rng.randint(150, 950), reorder_level=50)
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

        # Assign distinct customer purchasing tiers so RFM segmentation has clear behavioral clusters
        vip_customers = customers[:6]
        regular_customers = customers[6:15]
        dormant_customers = customers[15:]

        # 4. Create Orders across 365 days with realistic weekday B2B seasonality
        now = timezone.now()
        statuses = [Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.FULFILLED, Order.Status.INVOICED]
        vans = ["KQ Van KBZ 482Y", "KQ Logistics Van KCG 119Q", "Aviation Ramp Truck KDA 702P", "Airside Dispatch Van KBN 553T"]
        drivers = ["Driver J. Kamau", "Driver P. Ochieng", "Driver M. Mutua", "Driver D. Kiprop", "Driver E. Waweru"]

        invoices_created = 0
        payments_created = 0
        orders_created = 0

        # Generate weekday-weighted dates across the past 364 days
        candidate_days = list(range(0, 365))
        day_weights = []
        for d in candidate_days:
            dt = now - timedelta(days=d)
            # Mon-Fri (0-4) high B2B dispatch activity, Sat-Sun (5-6) lighter aviation catering top-ups
            day_weights.append(3.0 if dt.weekday() < 5 else 0.8)

        chosen_days = rng.choices(candidate_days, weights=day_weights, k=250)

        for idx, days_ago in enumerate(sorted(chosen_days, reverse=True)):
            if days_ago > 75 and rng.random() < 0.28:
                customer = rng.choice(dormant_customers)
            elif rng.random() < 0.48:
                customer = rng.choice(vip_customers)
            else:
                customer = rng.choice(regular_customers)

            order_date = now - timedelta(days=days_ago)
            order_status = statuses[idx % len(statuses)] if days_ago < 14 else rng.choice(
                [Order.Status.FULFILLED, Order.Status.INVOICED, Order.Status.INVOICED]
            )
            dispatch_notes = ""
            if order_status in [Order.Status.FULFILLED, Order.Status.INVOICED]:
                gate_pass = rng.randint(1000, 9999)
                dispatch_notes = f"{rng.choice(vans)} | {rng.choice(drivers)} | Gate Pass #{gate_pass}"

            order = Order.objects.create(
                customer=customer,
                status=order_status,
                fulfillment_notes=dispatch_notes,
            )
            Order.objects.filter(pk=order.pk).update(order_date=order_date)
            orders_created += 1

            is_spike_order = (idx % 23 == 0)
            num_items = rng.randint(2, 4) if customer in vip_customers else rng.randint(1, 3)
            order_subtotal = Decimal("0.00")

            for item_i in range(num_items):
                product = rng.choice(products)
                base_qty = rng.randint(20, 48) if customer in vip_customers else rng.randint(10, 32)
                if is_spike_order and item_i == 0:
                    quantity = rng.randint(220, 420)  # Deliberate anomalous spike (~4.5% of orders)
                else:
                    quantity = base_qty
                item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.unit_price,
                )
                order_subtotal += Decimal(str(item.line_total))

            # 5. Create Invoices and Payments for INVOICED orders
            if order_status == Order.Status.INVOICED:
                vat = round(order_subtotal * Decimal("0.16"), 2)
                total_invoiced = order_subtotal + vat
                invoice = Invoice.objects.create(
                    order=order,
                    total_amount=total_invoiced,
                )
                Invoice.objects.filter(pk=invoice.pk).update(issue_date=order_date.date())
                invoices_created += 1

                if customer.account_type == "KQ Internal Department":
                    p_method = Payment.Method.INTERNAL_JOURNAL
                    ref_code = f"JRNL-KQ-{rng.randint(10000, 99999)}"
                elif customer.account_type == "Corporate Client":
                    p_method = rng.choice([Payment.Method.BANK_TRANSFER, Payment.Method.MPESA, Payment.Method.CHEQUE])
                    ref_code = f"EFT-{rng.choice(['KCB', 'EQT', 'SCB'])}-{rng.randint(10000, 99999)}"
                elif customer.account_type == "Distributor":
                    p_method = rng.choice([Payment.Method.MPESA, Payment.Method.BANK_TRANSFER, Payment.Method.CASH])
                    ref_code = f"MPESA-Q{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(10000, 99999)}"
                else:
                    p_method = rng.choice([Payment.Method.BANK_TRANSFER, Payment.Method.CHEQUE])
                    ref_code = f"TREASURY-CHQ-{rng.randint(10000, 99999)}"

                roll = rng.random()
                if roll < 0.65:
                    pay_date = min(now.date(), (order_date + timedelta(days=rng.randint(1, 15))).date())
                    Payment.objects.create(
                        invoice=invoice,
                        amount=total_invoiced,
                        payment_date=pay_date,
                        method=p_method,
                        reference=ref_code,
                        notes="Settled in full per contract",
                    )
                    payments_created += 1
                elif roll < 0.88:
                    partial_amount = round(total_invoiced * Decimal(str(rng.uniform(0.35, 0.70))), 2)
                    pay_date = min(now.date(), (order_date + timedelta(days=rng.randint(1, 10))).date())
                    Payment.objects.create(
                        invoice=invoice,
                        amount=partial_amount,
                        payment_date=pay_date,
                        method=p_method,
                        reference=f"{ref_code}-PART",
                        notes="Partial installment",
                    )
                    payments_created += 1

        # 6. Standardize SystemSettings and train all 3 ML models in sync
        from analytics.models import SystemSetting
        from analytics.ml.pipeline import run_all_ml_pipelines

        cfg = SystemSetting.get_settings()
        cfg.forecast_horizon_days = 30
        cfg.forecast_confidence = 0.85
        cfg.anomaly_contamination = 0.05
        cfg.customer_segment_clusters = 4
        cfg.save()

        runs = run_all_ml_pipelines(user=None)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded demo data: {orders_created} orders, "
                f"{invoices_created} invoices, {payments_created} payments, and trained all 3 ML models "
                f"(Forecast MAE={runs['forecasting'].metrics.get('mae')}, "
                f"Silhouette={runs['segmentation'].metrics.get('silhouette_score')}, "
                f"Anomalies={runs['anomaly'].metrics.get('anomalies_detected')})."
            )
        )
