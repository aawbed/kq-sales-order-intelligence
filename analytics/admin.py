from django.contrib import admin

from .models import (
    CustomerSegmentRecord,
    DemandForecastRecord,
    MLModelRun,
    OrderAnomalyRecord,
    Report,
    SystemSetting,
)

@admin.register(MLModelRun)
class MLModelRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "model_type", "run_date", "status", "trained_by")
    list_filter = ("model_type", "status", "run_date")
    readonly_fields = ("run_date", "metrics", "parameters")

@admin.register(DemandForecastRecord)
class DemandForecastRecordAdmin(admin.ModelAdmin):
    list_display = ("forecast_id", "model_run", "forecast_date", "predicted_quantity", "confidence_lower", "confidence_upper")
    list_filter = ("forecast_date", "model_run")

@admin.register(CustomerSegmentRecord)
class CustomerSegmentRecordAdmin(admin.ModelAdmin):
    list_display = ("segment_id", "model_run", "customer", "cluster_label", "recency_days", "order_frequency", "monetary_spend")
    list_filter = ("cluster_label", "model_run")
    search_fields = ("customer__name",)

@admin.register(OrderAnomalyRecord)
class OrderAnomalyRecordAdmin(admin.ModelAdmin):
    list_display = ("anomaly_id", "model_run", "order", "anomaly_score", "review_status", "reviewed_by", "reviewed_at")
    list_filter = ("review_status", "model_run")
    search_fields = ("order__order_id", "order__customer__name")

admin.site.register(Report)
admin.site.register(SystemSetting)
