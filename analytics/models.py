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
