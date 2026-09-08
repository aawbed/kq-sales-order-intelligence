"""
Orchestrates the three ML functions (forecasting, anomaly detection,
customer segmentation) behind a single entry point used by
analytics.models.Report.generate() and the Sales Dashboard view.
"""

from analytics.ml.anomaly_detection import detect_anomalies
from analytics.ml.customer_segmentation import segment_customers
from analytics.ml.forecasting import forecast_demand


def run_report_pipeline(report_type, **kwargs):
    """Dispatch to the appropriate ML module based on the requested report type."""
    from analytics.models import Report

    if report_type == Report.ReportType.DEMAND_FORECAST:
        return forecast_demand(**kwargs)
    if report_type == Report.ReportType.CUSTOMER_SEGMENTATION:
        return segment_customers(**kwargs)
    if report_type == Report.ReportType.SALES_TREND:
        return detect_anomalies(**kwargs)
    raise ValueError(f"Unknown report_type: {report_type}")
