from django.core.management.base import BaseCommand

from analytics.ml.anomaly_detection import detect_anomalies
from analytics.ml.customer_segmentation import segment_customers
from analytics.ml.forecasting import forecast_demand
from analytics.ml.pipeline import (
    train_and_persist_anomalies,
    train_and_persist_forecasting,
    train_and_persist_segmentation,
)
from orders.models import Customer, Order


class Command(BaseCommand):
    help = "Run, inspect, and optionally persist any of the 3 machine learning models."

    def add_arguments(self, parser):
        parser.add_argument(
            "model_name",
            type=str,
            choices=["forecast", "segmentation", "anomaly", "all"],
            help="Name of the model to run: 'forecast', 'segmentation', 'anomaly', or 'all'",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of result rows to display (default: 10)",
        )
        parser.add_argument(
            "--persist",
            action="store_true",
            help="Persist new MLModelRun and prediction records into the database.",
        )

    def handle(self, *args, **options):
        model_name = options["model_name"]
        limit = options["limit"]
        persist = options["persist"]

        if model_name in ["forecast", "all"]:
            self.run_forecasting(limit, persist=persist)

        if model_name in ["segmentation", "all"]:
            self.run_segmentation(limit, persist=persist)

        if model_name in ["anomaly", "all"]:
            self.run_anomaly(limit, persist=persist)

    def run_forecasting(self, limit, persist=False):
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 65))
        self.stdout.write(self.style.MIGRATE_HEADING("  MODEL 1: DEMAND FORECASTING (SEASONAL SARIMAX)"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 65))
        self.stdout.write("  File:       analytics/ml/forecasting.py")
        self.stdout.write("  Algorithm:  SARIMAX(order=(1,1,1), seasonal_order=(1,0,1,7))")
        self.stdout.write("  Target:     Daily aggregate order volume (units)")
        self.stdout.write("-" * 65)

        if persist:
            run, records = train_and_persist_forecasting(user=None)
            results = [
                {"date": r.forecast_date.strftime("%Y-%m-%d"), "predicted_quantity": r.predicted_quantity}
                for r in records
            ]
            metrics = run.metrics
        else:
            orders = Order.objects.all()
            results, metrics, _ = forecast_demand(orders, periods=30, return_details=True)

        if not results:
            self.stdout.write(self.style.WARNING("  Insufficient data for forecasting."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"  Generated {len(results)}-day forecast | MAE={metrics.get('mae')} | "
                f"RMSE={metrics.get('rmse')} | WMAPE={metrics.get('mape')}%\n"
            )
        )
        for r in results[:limit]:
            self.stdout.write(f"  {r['date']:<15} | {r['predicted_quantity']:<30.1f}")

    def run_segmentation(self, limit, persist=False):
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 65))
        self.stdout.write(self.style.MIGRATE_HEADING("  MODEL 2: CUSTOMER SEGMENTATION (RFM + K-MEANS)"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 65))
        self.stdout.write("  File:       analytics/ml/customer_segmentation.py")
        self.stdout.write("  Algorithm:  K-Means Clustering + StandardScaler")
        self.stdout.write("  Features:   Recency (days), Frequency (orders), Monetary (KSh)")
        self.stdout.write("-" * 65)

        if persist:
            run, _ = train_and_persist_segmentation(user=None)
            customers = Customer.objects.prefetch_related("orders__items").all()
            results = segment_customers(customers)
            metrics = run.metrics
        else:
            customers = Customer.objects.prefetch_related("orders__items").all()
            results, metrics, _ = segment_customers(customers, return_details=True)

        if not results:
            self.stdout.write(self.style.WARNING("  Insufficient data for segmentation."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"  Segmented {len(results)} accounts | k={metrics.get('k')} | "
                f"Silhouette={metrics.get('silhouette_score')}\n"
            )
        )
        for s in results[:limit]:
            self.stdout.write(
                f"  {s['customer_name'][:32]:<32} | "
                f"{s['recency']:<8} | "
                f"{s['frequency']:<6} | "
                f"KSh {s['monetary']:<12,.2f} | "
                f"{s['cluster_label']:<18}"
            )

    def run_anomaly(self, limit, persist=False):
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 65))
        self.stdout.write(self.style.MIGRATE_HEADING("  MODEL 3: ORDER ANOMALY DETECTION (ISOLATION FOREST)"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 65))
        self.stdout.write("  File:       analytics/ml/anomaly_detection.py")
        self.stdout.write("  Algorithm:  Isolation Forest + StandardScaler")
        self.stdout.write("  Features:   Quantity, Total Value, Customer Frequency, Customer Value Z-Score")
        self.stdout.write("-" * 65)

        if persist:
            run, _ = train_and_persist_anomalies(user=None)
            orders = Order.objects.select_related("customer").prefetch_related("items__product").all()
            results = detect_anomalies(orders)
            metrics = run.metrics
        else:
            orders = Order.objects.select_related("customer").prefetch_related("items__product").all()
            results, metrics, _ = detect_anomalies(orders, return_details=True)

        if not results:
            self.stdout.write(self.style.SUCCESS("  No anomalies detected in the dataset."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"  Found {len(results)} / {metrics.get('total_orders')} flagged orders "
                f"({metrics.get('contamination_rate', 0) * 100:.1f}%)\n"
            )
        )
        for a in results[:limit]:
            self.stdout.write(
                f"  KQ-{a['order_id']:<7} | "
                f"{a['customer_name'][:32]:<32} | "
                f"{a['anomaly_score']:<10.4f} | "
                f"{a['explanation']}"
            )
