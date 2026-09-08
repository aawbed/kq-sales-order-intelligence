from django.conf import settings
from django.db import models


class Report(models.Model):
    """Corresponds to the REPORT entity in the ERD / class diagram."""

    class ReportType(models.TextChoices):
        SALES_TREND = "sales_trend", "Sales Trend"
        CUSTOMER_SEGMENTATION = "customer_segmentation", "Customer Segmentation"
        DEMAND_FORECAST = "demand_forecast", "Demand Forecast"

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
