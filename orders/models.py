from django.conf import settings
from django.db import models


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

    invoice_id = models.AutoField(primary_key=True)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    issue_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Invoice #{self.invoice_id} for Order #{self.order_id}"

    @classmethod
    def generate(cls, order):
        """Corresponds to generate() in the class diagram."""
        total = sum(item.line_total for item in order.items.all())
        invoice = cls.objects.create(order=order, total_amount=total)
        order.update_status(Order.Status.INVOICED)
        return invoice


class Payment(models.Model):
    """Corresponds to the PAYMENT entity in the ERD / class diagram."""

    payment_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    method = models.CharField(max_length=30)

    def __str__(self):
        return f"Payment of {self.amount} for Invoice #{self.invoice_id}"
