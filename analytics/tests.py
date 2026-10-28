from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from analytics.ml.pipeline import (
    train_and_persist_anomalies,
    train_and_persist_forecasting,
    train_and_persist_segmentation,
)
from analytics.models import (
    MLModelRun,
    OrderAnomalyRecord,
    SystemSetting,
)
from inventory.models import Product, Stock
from orders.models import Customer, Order, OrderItem

User = get_user_model()


class AnalyticsAndMLUnitTests(TestCase):
    def setUp(self):
        self.role_op = Role.objects.create(role_name=Role.RoleName.OPERATIONS_MANAGER)
        self.user = User.objects.create_user(
            username="ops_tester",
            password="Password123!",
            role=self.role_op,
        )

        self.product = Product.objects.create(
            name="500ml Water Case",
            unit_price=Decimal("600.00"),
        )
        Stock.objects.create(product=self.product, quantity_on_hand=5000, reorder_level=500)

        self.customers = []
        for i in range(10):
            c = Customer.objects.create(
                name=f"Customer {i+1}",
                contact_info=f"cust{i+1}@example.com",
                account_type="Corporate Client" if i % 2 == 0 else "Distributor",
            )
            self.customers.append(c)

        now = timezone.now()
        for idx in range(30):
            order_date = now - timedelta(days=30 - idx)
            cust = self.customers[idx % len(self.customers)]
            order = Order.objects.create(
                customer=cust,
                created_by=self.user,
                status=Order.Status.CONFIRMED,
            )
            Order.objects.filter(pk=order.pk).update(order_date=order_date)

            qty = 500 if idx == 28 else (10 + (idx % 5) * 5)
            OrderItem.objects.create(
                order=order,
                product=self.product,
                quantity=qty,
                unit_price=Decimal("600.00"),
            )

    def test_system_settings_singleton(self):
        cfg = SystemSetting.get_settings()
        self.assertEqual(cfg.pk, 1)
        cfg.forecast_horizon_days = 21
        cfg.save()

        cfg_reloaded = SystemSetting.get_settings()
        self.assertEqual(cfg_reloaded.forecast_horizon_days, 21)

    def test_sarimax_forecasting_pipeline_and_persistence(self):
        run, records = train_and_persist_forecasting(user=self.user, periods=14)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.model_type, MLModelRun.ModelType.FORECASTING)
        self.assertEqual(len(records), 14)
        self.assertIn("mae", run.metrics)
        self.assertIn("rmse", run.metrics)
        self.assertEqual(run.parameters.get("seasonal_order"), [1, 0, 1, 7])
        self.assertEqual(run.parameters.get("display_algorithm"), "SARIMAX (1,1,1)(1,0,1,7)")

        first_rec = records[0]
        self.assertGreater(first_rec.predicted_quantity, 0)
        self.assertEqual(first_rec.model_run, run)

    def test_kmeans_customer_segmentation_pipeline_and_persistence(self):
        run, records = train_and_persist_segmentation(user=self.user, n_clusters=3)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.model_type, MLModelRun.ModelType.SEGMENTATION)
        self.assertGreater(len(records), 0)
        self.assertIn("silhouette_score", run.metrics)

        seg_record = records[0]
        self.assertIsNotNone(seg_record.cluster_label)
        self.assertGreaterEqual(seg_record.monetary_spend, 0)

    def test_isolation_forest_anomaly_detection_and_review_workflow(self):
        run, records = train_and_persist_anomalies(user=self.user, contamination=0.1)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.model_type, MLModelRun.ModelType.ANOMALY)
        self.assertIn("total_orders", run.metrics)
        self.assertIn("anomalies_detected", run.metrics)
        self.assertIn("Customer Value Z-Score", run.parameters.get("features", []))

        self.assertGreater(len(records), 0)
        anomaly = records[0]
        self.assertEqual(anomaly.review_status, OrderAnomalyRecord.ReviewStatus.PENDING)

        # Verify review_anomaly view updates live precision AND blocks external open redirects
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("analytics:review_anomaly", args=[anomaly.anomaly_id]),
            {
                "review_status": OrderAnomalyRecord.ReviewStatus.CONFIRMED,
                "review_notes": "Confirmed spike due to major airport VIP summit.",
                "next": "https://evil.example.com/phish",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("analytics:dashboard"))

        anomaly.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(anomaly.review_status, OrderAnomalyRecord.ReviewStatus.CONFIRMED)
        self.assertEqual(run.metrics.get("precision"), 1.0)

    def test_model_performance_displays_dynamic_algorithm_and_reports_have_complete_columns(self):
        train_and_persist_forecasting(user=self.user, periods=14)
        train_and_persist_segmentation(user=self.user, n_clusters=3)
        train_and_persist_anomalies(user=self.user, contamination=0.1)

        self.client.force_login(self.user)
        perf_resp = self.client.get(reverse("analytics:model_performance"))
        self.assertEqual(perf_resp.status_code, 200)
        perf_html = perf_resp.content.decode("utf-8")
        self.assertIn("SARIMAX (1,1,1)(1,0,1,7)", perf_html)
        self.assertIn("Customer Value Z-Score", perf_html)

        # Verify Anomaly Alerts report populates real dates, account types, and values
        anom_resp = self.client.get(reverse("analytics:generate_reports") + "?report_type=anomaly_alerts")
        self.assertEqual(anom_resp.status_code, 200)
        anom_html = anom_resp.content.decode("utf-8")
        self.assertNotIn("<td>N/A</td>", anom_html)

        # Verify Customer Segments report populates real account types (no N/A)
        seg_resp = self.client.get(reverse("analytics:generate_reports") + "?report_type=customer_segments")
        self.assertEqual(seg_resp.status_code, 200)
        seg_html = seg_resp.content.decode("utf-8")
        self.assertNotIn("<td>N/A</td>", seg_html)
