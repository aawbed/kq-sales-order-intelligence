"""
Orchestrates the three ML functions (forecasting, anomaly detection,
customer segmentation) behind a single entry point used by
analytics.models.Report.generate() and the Sales Dashboard view.
"""

from datetime import datetime
from django.db import transaction
from django.utils import timezone

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


def train_and_persist_forecasting(user=None, periods=None):
    """
    Fit SARIMAX model, persist run metadata in MLModelRun,
    and save individual forecast points in DemandForecastRecord.
    """
    from analytics.models import DemandForecastRecord, MLModelRun, SystemSetting
    from orders.models import Order

    cfg = SystemSetting.get_settings()
    periods = periods or cfg.forecast_horizon_days
    orders = Order.objects.all()

    results, metrics, params = forecast_demand(orders, periods=periods, return_details=True)

    with transaction.atomic():
        run = MLModelRun.objects.create(
            model_type=MLModelRun.ModelType.FORECASTING,
            status="completed" if results else "failed",
            metrics=metrics,
            parameters=params,
            trained_by=user,
        )

        records = []
        for row in results:
            d_val = row["date"]
            if isinstance(d_val, str):
                d_val = datetime.strptime(d_val, "%Y-%m-%d").date()
            records.append(
                DemandForecastRecord(
                    model_run=run,
                    forecast_date=d_val,
                    predicted_quantity=row.get("predicted_quantity", 0.0),
                    confidence_lower=row.get("confidence_lower", 0.0),
                    confidence_upper=row.get("confidence_upper", 0.0),
                )
            )
        if records:
            DemandForecastRecord.objects.bulk_create(records)

    return run, records


def train_and_persist_segmentation(user=None, n_clusters=None):
    """
    Run K-Means RFM clustering, persist run metadata in MLModelRun,
    and save customer cluster assignments in CustomerSegmentRecord.
    """
    from analytics.models import CustomerSegmentRecord, MLModelRun, SystemSetting
    from orders.models import Customer

    cfg = SystemSetting.get_settings()
    n_clusters = n_clusters or cfg.customer_segment_clusters
    customers = Customer.objects.prefetch_related("orders__items").all()

    results, metrics, params = segment_customers(customers, n_clusters=n_clusters, return_details=True)

    with transaction.atomic():
        run = MLModelRun.objects.create(
            model_type=MLModelRun.ModelType.SEGMENTATION,
            status="completed" if results else "failed",
            metrics=metrics,
            parameters=params,
            trained_by=user,
        )

        records = []
        for row in results:
            try:
                cust_inst = Customer.objects.get(pk=row["customer_id"])
            except Customer.DoesNotExist:
                continue

            records.append(
                CustomerSegmentRecord(
                    model_run=run,
                    customer=cust_inst,
                    recency_days=int(row.get("recency", 0)),
                    order_frequency=int(row.get("frequency", 0)),
                    monetary_spend=row.get("monetary", 0.0),
                    cluster_id=int(row.get("cluster", 0)),
                    cluster_label=str(row.get("cluster_label", "Regular")),
                )
            )
        if records:
            CustomerSegmentRecord.objects.bulk_create(records)

    return run, records


def train_and_persist_anomalies(user=None, contamination=None):
    """
    Run Isolation Forest, persist run metadata in MLModelRun,
    and save flagged anomaly records with human review preservation.
    """
    from analytics.models import MLModelRun, OrderAnomalyRecord, SystemSetting
    from orders.models import Order

    cfg = SystemSetting.get_settings()
    contamination = contamination or cfg.anomaly_contamination
    orders = Order.objects.select_related("customer").prefetch_related("items").all()

    results, metrics, params = detect_anomalies(orders, contamination=contamination, return_details=True)

    # Compute human review feedback loop precision metrics
    reviewed_qs = OrderAnomalyRecord.objects.exclude(review_status=OrderAnomalyRecord.ReviewStatus.PENDING)
    total_reviewed = reviewed_qs.count()
    confirmed_count = reviewed_qs.filter(review_status=OrderAnomalyRecord.ReviewStatus.CONFIRMED).count()
    precision = round(confirmed_count / total_reviewed, 4) if total_reviewed > 0 else None

    metrics["reviewed_count"] = total_reviewed
    metrics["confirmed_count"] = confirmed_count
    metrics["precision"] = precision

    # Collect previous human reviews to preserve audit decisions across retrains
    previous_reviews = {
        rec.order_id: (rec.review_status, rec.reviewed_by, rec.reviewed_at, rec.review_notes)
        for rec in reviewed_qs
    }

    with transaction.atomic():
        run = MLModelRun.objects.create(
            model_type=MLModelRun.ModelType.ANOMALY,
            status="completed" if results or len(orders) < 5 else "failed",
            metrics=metrics,
            parameters=params,
            trained_by=user,
        )

        records = []
        for row in results:
            try:
                order_inst = Order.objects.get(pk=row["order_id"])
            except Order.DoesNotExist:
                continue

            status = OrderAnomalyRecord.ReviewStatus.PENDING
            rev_by = None
            rev_at = None
            rev_notes = ""

            if order_inst.order_id in previous_reviews:
                status, rev_by, rev_at, rev_notes = previous_reviews[order_inst.order_id]

            records.append(
                OrderAnomalyRecord(
                    model_run=run,
                    order=order_inst,
                    anomaly_score=float(row.get("anomaly_score", 0.0)),
                    is_anomaly=bool(row.get("is_anomaly", True)),
                    explanation=str(row.get("explanation", "")),
                    review_status=status,
                    reviewed_by=rev_by,
                    reviewed_at=rev_at,
                    review_notes=rev_notes,
                )
            )
        if records:
            OrderAnomalyRecord.objects.bulk_create(records)

    return run, records


def run_all_ml_pipelines(user=None):
    """Run and persist all three ML pipelines (SARIMAX, K-Means, Isolation Forest)."""
    forecast_run, _ = train_and_persist_forecasting(user=user)
    segment_run, _ = train_and_persist_segmentation(user=user)
    anomaly_run, _ = train_and_persist_anomalies(user=user)
    return {
        "forecasting": forecast_run,
        "segmentation": segment_run,
        "anomaly": anomaly_run,
    }
