from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Customer(models.Model):
    """
    Corresponds to the CUSTOMER entity in the ERD / class diagram.
    Represents the internal department, catering unit, or external
    distributor placing water sales orders with KQ (not an airline
    passenger — see the project's customer definition discussion).
    """

    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    contact_info = models.CharField(max_length=100)
    account_type = models.CharField(max_length=30)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def place_order(self):
        """Placeholder for order-placement business logic (placeOrder() in class diagram)."""
        raise NotImplementedError

    def view_order_history(self):
        """Placeholder for order-history retrieval (viewOrderHistory() in class diagram)."""
        return self.orders.all()


class Order(models.Model):
    """Corresponds to the ORDER entity in the ERD / class diagram."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        FULFILLED = "fulfilled", "Fulfilled"
        INVOICED = "invoiced", "Invoiced"

    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="orders_created"
    )

    class Meta:
        ordering = ["-order_date"]

    def __str__(self):
        return f"Order #{self.order_id} — {self.customer.name}"

    def add_item(self, product, quantity, unit_price):
        """Corresponds to addItem() in the class diagram."""
        return self.items.create(product=product, quantity=quantity, unit_price=unit_price)

    def update_status(self, new_status):
        """Corresponds to updateStatus() in the class diagram."""
        self.status = new_status
        self.save(update_fields=["status"])


class OrderItem(models.Model):
    """Corresponds to the ORDER_ITEM entity in the ERD / class diagram."""

    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("inventory.Product", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order #{self.order_id})"


class Invoice(models.Model):
    """Corresponds to the INVOICE entity in the ERD / class diagram."""

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"

    invoice_id = models.AutoField(primary_key=True)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    issue_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-issue_date", "-invoice_id"]

    def __str__(self):
        return f"Invoice #{self.invoice_id} for Order #{self.order_id}"

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.order.items.all())

    @property
    def vat_amount(self):
        return round(Decimal(str(self.subtotal)) * Decimal("0.16"), 2)

    @classmethod
    def generate(cls, order):
        """Corresponds to generate() in the class diagram (with 16% VAT included)."""
        subtotal = sum(item.line_total for item in order.items.all())
        vat = round(Decimal(str(subtotal)) * Decimal("0.16"), 2)
        total = Decimal(str(subtotal)) + vat
        invoice = cls.objects.create(order=order, total_amount=total)
        order.update_status(Order.Status.INVOICED)
        return invoice

    @property
    def amount_paid(self):
        total = self.payments.aggregate(models.Sum("amount"))["amount__sum"]
        return total or Decimal("0.00")

    @property
    def balance(self):
        bal = Decimal(str(self.total_amount)) - self.amount_paid
        return max(Decimal("0.00"), bal)

    @property
    def payment_status(self):
        paid = self.amount_paid
        total = Decimal(str(self.total_amount))
        if paid <= 0:
            return self.PaymentStatus.UNPAID
        elif paid < total:
            return self.PaymentStatus.PARTIALLY_PAID
        else:
            return self.PaymentStatus.PAID

    def get_payment_status_display(self):
        status_map = {
            self.PaymentStatus.UNPAID: "Unpaid",
            self.PaymentStatus.PARTIALLY_PAID: "Partially Paid",
            self.PaymentStatus.PAID: "Paid in Full",
        }
        return status_map.get(self.payment_status, "Unpaid")


class Payment(models.Model):
    """Corresponds to the PAYMENT entity in the ERD / class diagram."""

    class Method(models.TextChoices):
        MPESA = "mpesa", "M-Pesa (Paybill)"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"
        INTERNAL_JOURNAL = "internal_journal", "Internal Journal Transfer"

    payment_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.MPESA)
    reference = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g. M-Pesa transaction code, Cheque #, or Journal Ref",
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_recorded",
    )

    class Meta:
        ordering = ["-payment_date", "-payment_id"]

    def __str__(self):
        return f"Payment #{self.payment_id} of KSh {self.amount} ({self.get_method_display()}) for Invoice #{self.invoice_id}"
