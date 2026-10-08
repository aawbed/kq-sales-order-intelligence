from django.conf import settings
from django.db import models


class Report(models.Model):
    """Corresponds to the REPORT entity in the ERD / class diagram."""

    class ReportType(models.TextChoices):
        SALES_SUMMARY = "sales_summary", "Sales Summary"
        DEMAND_FORECAST = "demand_forecast", "Demand Forecast Matrix"
        ANOMALY_ALERTS = "anomaly_alerts", "Anomaly Alerts"
        CUSTOMER_SEGMENTS = "customer_segments", "Customer Segments (RFM)"
        ACCOUNTS_RECEIVABLE = "accounts_receivable", "Accounts Receivable Summary"
        SALES_TREND = "sales_trend", "Sales Trend"
        CUSTOMER_SEGMENTATION = "customer_segmentation", "Customer Segmentation"

    report_id = models.AutoField(primary_key=True)
    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    generated_date = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reports_generated"
    )
    data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.get_report_type_display()} — {self.generated_date:%Y-%m-%d}"

    @classmethod
    def generate(cls, report_type, generated_by=None, **kwargs):
        """Corresponds to generate() in the class diagram. Delegates to analytics.ml.pipeline."""
        from analytics.ml.pipeline import run_report_pipeline

        data = run_report_pipeline(report_type, **kwargs)
        return cls.objects.create(report_type=report_type, generated_by=generated_by, data=data)


class SystemSetting(models.Model):
    """
    Figure 3.7k: System Administrator — System Configuration Parameters.
    Stores configurable machine learning hyperparameters and automated notification preferences.
    """

    forecast_confidence = models.FloatField(
        default=0.85,
        help_text="Statistical confidence threshold for forecasting (0.50 - 0.99).",
    )
    forecast_horizon_days = models.PositiveIntegerField(
        default=30,
        help_text="Demand forecast horizon in days (7 - 90).",
    )
    forecast_cache_timeout = models.PositiveIntegerField(
        default=60,
        help_text="Forecasting computation cache timeout in minutes (5 - 1440).",
    )
    anomaly_contamination = models.FloatField(
        default=0.05,
        help_text="Expected proportion of anomalies in order stream (0.01 - 0.20).",
    )
    customer_segment_clusters = models.PositiveIntegerField(
        default=3,
        help_text="Number of behavioral RFM clusters (2 - 6).",
    )
    email_alerts_anomaly = models.BooleanField(
        default=True,
        help_text="Send immediate email alerts to Operations Manager on high-priority ML anomalies.",
    )
    stock_alerts_warehouse = models.BooleanField(
        default=True,
        help_text="Notify Warehouse Officer immediately on critical low stock components.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settings_updated",
    )

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return f"System Configuration (Updated {self.updated_at:%Y-%m-%d %H:%M})"

    @classmethod
    def get_settings(cls):
        """Retrieve the singleton settings record, creating default if not found."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class MLModelRun(models.Model):
    """
    Model Training feedback loop: Tracks execution and retraining runs of ML models,
    storing validation metrics (MAE, RMSE, MAPE, Silhouette, Precision) and hyperparameters.
    """

    class ModelType(models.TextChoices):
        FORECASTING = "forecasting", "Demand Forecasting (SARIMAX)"
        ANOMALY = "anomaly", "Anomaly Detection (Isolation Forest)"
        SEGMENTATION = "segmentation", "Customer Segmentation (K-Means)"

    run_id = models.AutoField(primary_key=True)
    model_type = models.CharField(max_length=30, choices=ModelType.choices)
    run_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="completed")
    metrics = models.JSONField(default=dict, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    trained_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="model_runs",
    )

    class Meta:
        ordering = ["-run_date"]
        verbose_name = "ML Model Run"
        verbose_name_plural = "ML Model Runs"

    def __str__(self):
        return f"{self.get_model_type_display()} — Run #{self.run_id} ({self.run_date:%Y-%m-%d %H:%M})"


class DemandForecastRecord(models.Model):
    """
    Persisted structured output of SARIMAX demand forecasting models.
    """

    forecast_id = models.AutoField(primary_key=True)
    model_run = models.ForeignKey(MLModelRun, on_delete=models.CASCADE, related_name="forecast_records")
    forecast_date = models.DateField(db_index=True)
    predicted_quantity = models.FloatField()
    confidence_lower = models.FloatField(default=0.0)
    confidence_upper = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["forecast_date"]
        verbose_name = "Demand Forecast Record"
        verbose_name_plural = "Demand Forecast Records"

    def __str__(self):
        return f"Forecast {self.forecast_date}: {self.predicted_quantity:.1f} units"


class CustomerSegmentRecord(models.Model):
    """
    Persisted structured output of K-Means behavioral RFM customer segmentation.
    """

    segment_id = models.AutoField(primary_key=True)
    model_run = models.ForeignKey(MLModelRun, on_delete=models.CASCADE, related_name="segment_records")
    customer = models.ForeignKey("orders.Customer", on_delete=models.CASCADE, related_name="segment_records")
    recency_days = models.IntegerField()
    order_frequency = models.IntegerField()
    monetary_spend = models.DecimalField(max_digits=12, decimal_places=2)
    cluster_id = models.IntegerField()
    cluster_label = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cluster_id", "-monetary_spend"]
        verbose_name = "Customer Segment Record"
        verbose_name_plural = "Customer Segment Records"

    def __str__(self):
        return f"{self.customer.name} -> {self.cluster_label} (Cluster {self.cluster_id})"

    @property
    def customer_name(self):
        return self.customer.name if self.customer else "Unknown"

    @property
    def recency(self):
        return self.recency_days

    @property
    def frequency(self):
        return self.order_frequency

    @property
    def monetary(self):
        return self.monetary_spend


class OrderAnomalyRecord(models.Model):
    """
    Persisted structured output of Isolation Forest anomaly detection and human review loop.
    """

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending Review"
        CONFIRMED = "confirmed", "Confirmed Anomaly"
        FALSE_POSITIVE = "false_positive", "False Positive (Dismissed)"

    anomaly_id = models.AutoField(primary_key=True)
    model_run = models.ForeignKey(MLModelRun, on_delete=models.CASCADE, related_name="anomaly_records")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="anomaly_records")
    anomaly_score = models.FloatField()
    is_anomaly = models.BooleanField(default=True)
    explanation = models.TextField(blank=True, default="")
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order Anomaly Record"
        verbose_name_plural = "Order Anomaly Records"

    def __str__(self):
        return f"Order KQ-{self.order.order_id} ({self.get_review_status_display()}, Score: {self.anomaly_score:.3f})"

    @property
    def customer_name(self):
        return self.order.customer.name if self.order and self.order.customer else "Unknown"

