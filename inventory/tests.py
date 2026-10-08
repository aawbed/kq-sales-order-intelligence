from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Role
from core.models import Notification
from inventory.models import Product, Stock

User = get_user_model()


class InventoryAndStockTests(TestCase):
    def setUp(self):
        self.role_wh = Role.objects.create(role_name=Role.RoleName.WAREHOUSE_OFFICER)
        self.user_wh = User.objects.create_user(
            username="warehouse_user",
            password="Password123!",
            role=self.role_wh,
        )

        self.product = Product.objects.create(
            name="1L Bottle Case (12 Pack)",
            unit_price=Decimal("720.00"),
        )
        self.stock = Stock.objects.create(
            product=self.product,
            quantity_on_hand=150,
            reorder_level=50,
        )

    def test_product_and_stock_string_representation(self):
        self.assertEqual(str(self.product), "1L Bottle Case (12 Pack)")
        self.assertIn("150 on hand", str(self.stock))
        self.assertFalse(self.stock.is_low)

    def test_stock_level_adjustments(self):
        # Increase stock by 50
        new_level = self.stock.update_level(50, reason="Production batch landed")
        self.assertEqual(new_level, 200)
        self.assertEqual(self.stock.quantity_on_hand, 200)

        # Deduct stock by 80
        new_level = self.stock.update_level(-80, reason="Order dispatched")
        self.assertEqual(new_level, 120)
        self.assertEqual(self.stock.quantity_on_hand, 120)

        # Ensure stock never goes below zero
        new_level = self.stock.update_level(-500, reason="Mass write-off")
        self.assertEqual(new_level, 0)
        self.assertEqual(self.stock.quantity_on_hand, 0)
        self.assertTrue(self.stock.is_low)

    def test_low_stock_notification_trigger(self):
        # Reduce stock below reorder level (50)
        self.stock.update_level(-120)  # 150 - 120 = 30 (<= 50)
        self.assertTrue(self.stock.is_low)

        # Notification should have been dispatched to warehouse officer
        notification = Notification.objects.filter(
            recipient=self.user_wh,
            category=Notification.Category.LOW_STOCK,
        ).first()

        self.assertIsNotNone(notification)
        self.assertIn("Low Stock Alert", notification.title)
        self.assertIn("1L Bottle Case", notification.message)
