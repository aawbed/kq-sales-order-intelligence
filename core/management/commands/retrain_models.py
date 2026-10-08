"""
Management command to retrain machine learning models and record validation metrics.

Implements model retraining and evaluation feedback loop for:
1. Demand Forecasting (SARIMAX) -> MAE, RMSE, MAPE
2. Customer Segmentation (K-Means RFM) -> Silhouette Score, Inertia
3. Order Anomaly Detection (Isolation Forest) -> Contamination Rate, Precision from Human Reviews
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from analytics.ml.pipeline import (
    train_and_persist_forecasting,
    train_and_persist_segmentation,
    train_and_persist_anomalies,
)
from analytics.models import MLModelRun

User = get_user_model()


class Command(BaseCommand):
    help = "Retrain ML models (SARIMAX, K-Means, Isolation Forest) and update performance metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            choices=["all", "forecasting", "segmentation", "anomaly"],
            default="all",
            help="Specify which model to retrain: 'all', 'forecasting', 'segmentation', or 'anomaly'.",
        )
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Username to associate with this retraining run (optional).",
        )

    def handle(self, *args, **options):
        model_choice = options["model"]
        username = options["user"]

        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"User '{username}' not found. Training without user association."))

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING("  KQ SALES ORDER INTELLIGENCE — ML MODEL RETRAINING PIPELINE"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))

        if model_choice in ["forecasting", "all"]:
            self.retrain_forecasting(user)

        if model_choice in ["segmentation", "all"]:
            self.retrain_segmentation(user)

        if model_choice in ["anomaly", "all"]:
            self.retrain_anomaly(user)

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Model retraining pipeline completed successfully.\n"))

    def retrain_forecasting(self, user):
        self.stdout.write("\nRetraining Demand Forecasting (SARIMAX)...")
        run, records = train_and_persist_forecasting(user=user)
        m = run.metrics or {}
        self.stdout.write(self.style.SUCCESS(f"  -> Run #{run.run_id} created ({run.status.upper()})"))
        self.stdout.write(f"     Horizon: {run.parameters.get('periods', 30)} days ({len(records)} forecast points generated)")
        self.stdout.write(f"     Validation MAE:  {m.get('mae', 'N/A')}")
        self.stdout.write(f"     Validation RMSE: {m.get('rmse', 'N/A')}")
        self.stdout.write(f"     Validation MAPE: {m.get('mape', 'N/A')}%")
        self.stdout.write(f"     Training Sample: {m.get('sample_days', 0)} days")

    def retrain_segmentation(self, user):
        self.stdout.write("\nRetraining Customer Segmentation (K-Means RFM)...")
        run, records = train_and_persist_segmentation(user=user)
        m = run.metrics or {}
        self.stdout.write(self.style.SUCCESS(f"  -> Run #{run.run_id} created ({run.status.upper()})"))
        self.stdout.write(f"     Clusters (k): {run.parameters.get('n_clusters', 3)} ({len(records)} customer assignments)")
        self.stdout.write(f"     Silhouette Score: {m.get('silhouette_score', 'N/A')}")
        self.stdout.write(f"     Cluster Inertia:  {m.get('inertia', 'N/A')}")
        self.stdout.write(f"     Evaluated Accounts: {m.get('num_customers', 0)}")

    def retrain_anomaly(self, user):
        self.stdout.write("\nRetraining Order Anomaly Detection (Isolation Forest)...")
        run, records = train_and_persist_anomalies(user=user)
        m = run.metrics or {}
        precision_str = f"{m.get('precision') * 100:.1f}%" if m.get("precision") is not None else "Pending Human Reviews"
        self.stdout.write(self.style.SUCCESS(f"  -> Run #{run.run_id} created ({run.status.upper()})"))
        self.stdout.write(f"     Orders Analyzed:   {m.get('total_orders', 0)}")
        self.stdout.write(f"     Anomalies Flagged: {m.get('anomalies_detected', 0)} ({len(records)} stored records)")
        self.stdout.write(f"     Contamination Rate: {m.get('contamination_rate', 0.05)}")
        self.stdout.write(f"     Review Precision:  {precision_str}")
