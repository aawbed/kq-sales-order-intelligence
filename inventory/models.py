from django.db import models


class Product(models.Model):
    """Corresponds to the PRODUCT entity in the ERD / class diagram."""

    product_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Stock(models.Model):
    """Corresponds to the STOCK entity in the ERD / class diagram."""

    stock_id = models.AutoField(primary_key=True)
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="stock")
    quantity_on_hand = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name}: {self.quantity_on_hand} on hand"

    def update_level(self, offset, reason=""):
        """Corresponds to updateLevel() in the class diagram."""
        self.quantity_on_hand = max(0, self.quantity_on_hand + offset)
        self.save(update_fields=["quantity_on_hand"])
        return self.quantity_on_hand

    @property
    def is_low(self):
        return self.quantity_on_hand <= self.reorder_level
