import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib import messages
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from analytics.models import (
    CustomerSegmentRecord,
    DemandForecastRecord,
    MLModelRun,
    OrderAnomalyRecord,
    Report,
    SystemSetting,
)
from analytics.report_pdf import generate_report_pdf
from core.audit import log_action
from core.permissions import (
    operations_manager_required,
    operations_or_admin_required,
    system_administrator_required,
)
from inventory.models import Stock
from orders.models import Customer, Invoice, Order, OrderItem, Payment


@operations_manager_required
def dashboard(request):
    """Figure 3.7h: Operations Manager — Sales Dashboard with live KPIs and ML outputs."""
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # --- KPI Calculations ---
    # Total sales (Last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    recent_orders = Order.objects.filter(order_date__gte=thirty_days_ago)
    recent_revenue = OrderItem.objects.filter(
        order__in=recent_orders
    ).aggregate(
        total=models.Sum(models.F("quantity") * models.F("unit_price"))
    )["total"] or 0

    # Orders this week
    weekly_orders = Order.objects.filter(order_date__gte=week_ago).count()

    # Low stock alerts
    low_stock_count = Stock.objects.filter(
        quantity_on_hand__lte=models.F("reorder_level")
    ).count()

    # Active customers
    active_customers = Customer.objects.count()

    # --- Persisted ML Outputs ---
    system_cfg = SystemSetting.get_settings()
    forecast_horizon = system_cfg.forecast_horizon_days
    forecast_confidence = system_cfg.forecast_confidence

    # 1. SARIMAX Demand Forecast
    forecast_run = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.FORECASTING, status="completed"
    ).first()
    if not forecast_run:
        try:
            from analytics.ml.pipeline import train_and_persist_forecasting
            forecast_run, _ = train_and_persist_forecasting(user=request.user)
        except Exception:
            forecast_run = None

    forecast_records = (
        list(forecast_run.forecast_records.all()[:forecast_horizon])
        if forecast_run else []
    )
    forecast_labels = json.dumps([r.forecast_date.strftime("%Y-%m-%d") for r in forecast_records])
    forecast_values = json.dumps([round(float(r.predicted_quantity), 1) for r in forecast_records])

    # 2. Isolation Forest Anomalies
    anomaly_run = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.ANOMALY, status="completed"
    ).first()
    if not anomaly_run:
        try:
            from analytics.ml.pipeline import train_and_persist_anomalies
            anomaly_run, _ = train_and_persist_anomalies(user=request.user)
        except Exception:
            anomaly_run = None

    anomalies = []
    reviewed_anomalies = []
    if anomaly_run:
        anomalies = list(
            anomaly_run.anomaly_records.filter(
                review_status=OrderAnomalyRecord.ReviewStatus.PENDING
            ).select_related("order__customer", "reviewed_by").all()[:10]
        )
        reviewed_anomalies = list(
            anomaly_run.anomaly_records.exclude(
                review_status=OrderAnomalyRecord.ReviewStatus.PENDING
            ).select_related("order__customer", "reviewed_by").all()[:10]
        )

    # 3. K-Means Customer Segments
    segment_run = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.SEGMENTATION, status="completed"
    ).first()
    if not segment_run:
        try:
            from analytics.ml.pipeline import train_and_persist_segmentation
            segment_run, _ = train_and_persist_segmentation(user=request.user)
        except Exception:
            segment_run = None

    segments = (
        list(segment_run.segment_records.select_related("customer").all())
        if segment_run else []
    )

    context = {
        "recent_revenue": round(recent_revenue, 2),
        "weekly_orders": weekly_orders,
        "low_stock_count": low_stock_count,
        "active_customers": active_customers,
        "forecast_labels": forecast_labels,
        "forecast_values": forecast_values,
        "forecast_horizon": forecast_horizon,
        "forecast_confidence": int(forecast_confidence * 100),
        "forecast_run": forecast_run,
        "anomaly_run": anomaly_run,
        "segment_run": segment_run,
        "anomalies": anomalies,
        "reviewed_anomalies": reviewed_anomalies,
        "segments": segments,
    }
    return render(request, "analytics/dashboard.html", context)


@operations_manager_required
def generate_reports(request):
    """
    Figure 3.7i: Operations Manager — Generate Reports & Forecasts.
    Supports 5 report categories, date range filtering, live table preview,
    and export to CSV and branded PDF statements. Stores generation history.
    """
    report_type = request.GET.get("report_type", "sales_summary")
    date_from_str = request.GET.get("date_from", "")
    date_to_str = request.GET.get("date_to", "")
    action = request.GET.get("action", "preview")

    now = timezone.now()
    default_from = (now - timedelta(days=90)).date()
    default_to = now.date()

    try:
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else default_from
    except ValueError:
        date_from = default_from

    try:
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else default_to
    except ValueError:
        date_to = default_to

    title = "System Report"
    subtitle = f"Period: {date_from.strftime('%b %d, %Y')} to {date_to.strftime('%b %d, %Y')}"
    headers = []
    rows = []
    summary_text = ""

    all_orders = Order.objects.select_related("customer").prefetch_related("items__product").all()
    all_customers = Customer.objects.prefetch_related("orders__items").all()

    if report_type == "sales_summary":
        title = "Historical Sales & Fulfilment Summary"
        headers = ["Order #", "Order Date", "Customer Account", "Account Type", "Items Qty", "Subtotal (KES)", "VAT 16% (KES)", "Total (KES)", "Status"]
        filtered_orders = all_orders.filter(order_date__date__range=[date_from, date_to])
        total_rev = Decimal("0.00")
        total_units = 0

        for o in filtered_orders:
            o_units = sum(i.quantity for i in o.items.all())
            o_sub = sum(i.line_total for i in o.items.all())
            o_vat = round(Decimal(str(o_sub)) * Decimal("0.16"), 2)
            o_tot = Decimal(str(o_sub)) + o_vat
            total_rev += o_tot
            total_units += o_units

            rows.append([
                f"KQ-{o.order_id}",
                o.order_date.strftime("%Y-%m-%d"),
                o.customer.name,
                o.customer.account_type,
                o_units,
                f"{o_sub:,.2f}",
                f"{o_vat:,.2f}",
                f"{o_tot:,.2f}",
                o.get_status_display()
            ])
        summary_text = f"Total Orders: {len(rows)} | Total Water Units Demanded: {total_units:,} | Cumulative Billed Revenue: KSh {total_rev:,.2f}"

    elif report_type == "demand_forecast":
        title = "SARIMAX Predictive Water Demand Forecast Matrix"
        subtitle = "Projected daily catering water consumption (Next 30 Days)"
        headers = ["Forecast Date", "Day of Week", "Predicted Demand (Units)", "Recommended Production Target"]
        from analytics.ml.forecasting import forecast_demand
        try:
            fc_data = forecast_demand(all_orders)
        except Exception:
            fc_data = []

        total_fc = 0.0
        for item in fc_data[:30]:
            qty = round(float(item.get("predicted_quantity", 0)), 1)
            total_fc += qty
            dt_str = item.get("date", "")
            try:
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
                dow = dt_obj.strftime("%A")
            except Exception:
                dow = "N/A"
            rec_prod = round(qty * 1.15, 1)  # 15% safety stock buffer
            rows.append([dt_str, dow, f"{qty:,.1f}", f"{rec_prod:,.1f}"])
        summary_text = f"30-Day Cumulative Forecasted Volume: {total_fc:,.1f} units | Includes 15% catering safety buffer"

    elif report_type == "anomaly_alerts":
        title = "Order Anomaly Detection Audit Report"
        headers = ["Order #", "Customer Account", "Order Date", "Account Type", "Total Qty", "Order Value (KES)", "Anomaly Score", "Flag Status"]
        from analytics.ml.anomaly_detection import detect_anomalies
        try:
            anom_data = detect_anomalies(all_orders)
        except Exception:
            anom_data = []

        flagged_count = 0
        for item in anom_data:
            is_anom = item.get("is_anomaly", False)
            if is_anom:
                flagged_count += 1
            o_id = item.get("order_id", "")
            score = round(float(item.get("anomaly_score", 0)), 4)
            val = round(float(item.get("total_value", 0)), 2)
            qty = item.get("quantity", 0)
            rows.append([
                f"KQ-{o_id}",
                item.get("order_date", "")[:10],
                item.get("customer_name", "N/A"),
                item.get("account_type", "N/A"),
                f"{qty:,}",
                f"{val:,.2f}",
                f"{score:.4f}",
                "FLAGGED ANOMALY" if is_anom else "Normal"
            ])
        summary_text = f"Total Orders Analyzed: {len(rows)} | Orders Flagged for Review: {flagged_count} | Contamination Threshold: 5%"

    elif report_type == "customer_segments":
        title = "Customer Purchasing Behaviour & RFM Segmentation"
        headers = ["Customer Account", "Account Type", "Recency (Days)", "Frequency (Orders)", "Monetary Spend (KES)", "Assigned Cluster Segment"]
        from analytics.ml.customer_segmentation import segment_customers
        try:
            seg_data = segment_customers(all_customers)
        except Exception:
            seg_data = []

        for item in seg_data:
            rec = item.get("recency", 0)
            freq = item.get("frequency", 0)
            mon = round(float(item.get("monetary", 0)), 2)
            rows.append([
                item.get("customer_name", "N/A"),
                item.get("account_type", "N/A"),
                f"{rec} days",
                f"{freq} orders",
                f"KSh {mon:,.2f}",
                item.get("cluster_label", "Regular")
            ])
        summary_text = f"Total Customer Accounts Profiled: {len(rows)} | K-Means Clusters: VIP / High-Volume, Regular, At-Risk / Dormant"

    elif report_type == "accounts_receivable":
        title = "Accounts Receivable & Ageing Summary Report"
        headers = ["Invoice #", "Issue Date", "Customer Account", "Account Type", "Age (Days)", "Invoiced (KES)", "Paid (KES)", "Balance (KES)", "Status"]
        invs = Invoice.objects.filter(issue_date__range=[date_from, date_to]).select_related("order__customer").prefetch_related("payments").all()
        today = timezone.now().date()
        tot_inv = Decimal("0.00")
        tot_paid = Decimal("0.00")
        tot_bal = Decimal("0.00")

        for inv in invs:
            age = max(0, (today - inv.issue_date).days)
            t = Decimal(str(inv.total_amount))
            p = inv.amount_paid
            b = inv.balance
            tot_inv += t
            tot_paid += p
            tot_bal += b
            rows.append([
                f"#INV-{inv.invoice_id}",
                inv.issue_date.strftime("%Y-%m-%d"),
                inv.order.customer.name,
                inv.order.customer.account_type,
                f"{age}d",
                f"{t:,.2f}",
                f"{p:,.2f}",
                f"{b:,.2f}",
                inv.get_payment_status_display()
            ])
        summary_text = f"Total Invoiced: KSh {tot_inv:,.2f} | Total Collected: KSh {tot_paid:,.2f} | Outstanding Receivables: KSh {tot_bal:,.2f}"

    # Handle Exports
    clean_type = report_type.replace("_", "-")
    time_tag = now.strftime("%Y%m%d_%H%M")
    
    if action == "csv":
        out = StringIO()
        out.write('\ufeff')  # UTF-8 BOM for Microsoft Excel compatibility
        writer = csv.writer(out)
        writer.writerow([f"KENYA AIRWAYS — {title}"])
        writer.writerow([f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}", f"Period: {date_from} to {date_to}"])
        writer.writerow([])
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
        if summary_text:
            writer.writerow([])
            writer.writerow(["SUMMARY NOTES", summary_text])

        resp = HttpResponse(out.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="KQ_{clean_type}_{time_tag}.csv"'
        return resp

    if action == "pdf":
        pdf_bytes = generate_report_pdf(
            title=title,
            subtitle=subtitle,
            headers=headers,
            rows=rows,
            summary_text=summary_text,
            landscape_mode=True
        )
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="KQ_{clean_type}_{time_tag}.pdf"'
        return resp

    # Default: Preview in UI and log generated report
    if request.user.is_authenticated:
        Report.objects.create(
            report_type=report_type,
            generated_by=request.user,
            data={"rows_count": len(rows), "date_from": str(date_from), "date_to": str(date_to), "title": title}
        )

    context = {
        "report_type": report_type,
        "date_from": date_from.strftime("%Y-%m-%d"),
        "date_to": date_to.strftime("%Y-%m-%d"),
        "title": title,
        "subtitle": subtitle,
        "headers": headers,
        "rows": rows,
        "summary_text": summary_text,
        "report_types": [
            ("sales_summary", "Historical Sales Summary"),
            ("demand_forecast", "Demand Forecast Matrix (Next 30 Days)"),
            ("anomaly_alerts", "Anomaly Alerts Audit"),
            ("customer_segments", "Customer Segments (RFM)"),
            ("accounts_receivable", "Accounts Receivable Summary"),
        ],
    }
    return render(request, "analytics/generate_reports.html", context)


@system_administrator_required
def system_settings(request):
    """
    Figure 3.7k: System Administrator — System Configuration Parameters.
    Exposes configurable machine learning thresholds and automated notification preferences.
    """
    settings_obj = SystemSetting.get_settings()
    errors = {}

    if request.method == "POST":
        confidence_str = request.POST.get("forecast_confidence", "").strip()
        horizon_str = request.POST.get("forecast_horizon_days", "").strip()
        cache_timeout_str = request.POST.get("forecast_cache_timeout", "").strip()
        contamination_str = request.POST.get("anomaly_contamination", "").strip()
        clusters_str = request.POST.get("customer_segment_clusters", "").strip()
        email_alerts = request.POST.get("email_alerts_anomaly") == "on"
        stock_alerts = request.POST.get("stock_alerts_warehouse") == "on"

        # Validate confidence (0.50 - 0.99)
        try:
            confidence = float(confidence_str)
            if not (0.50 <= confidence <= 0.99):
                errors["forecast_confidence"] = "Confidence threshold must be between 0.50 and 0.99."
        except ValueError:
            errors["forecast_confidence"] = "Please enter a valid decimal number."

        # Validate horizon (7 - 90 days)
        try:
            horizon = int(horizon_str)
            if not (7 <= horizon <= 90):
                errors["forecast_horizon_days"] = "Forecast horizon must be between 7 and 90 days."
        except ValueError:
            errors["forecast_horizon_days"] = "Please enter a valid whole number of days."

        # Validate cache timeout (5 - 1440 mins)
        try:
            cache_timeout = int(cache_timeout_str)
            if not (5 <= cache_timeout <= 1440):
                errors["forecast_cache_timeout"] = "Cache timeout must be between 5 and 1440 minutes."
        except ValueError:
            errors["forecast_cache_timeout"] = "Please enter a valid whole number of minutes."

        # Validate anomaly contamination (0.01 - 0.20)
        try:
            contamination = float(contamination_str)
            if not (0.01 <= contamination <= 0.20):
                errors["anomaly_contamination"] = "Contamination rate must be between 0.01 (1%) and 0.20 (20%)."
        except ValueError:
            errors["anomaly_contamination"] = "Please enter a valid decimal rate."

        # Validate clusters (2 - 6)
        try:
            clusters = int(clusters_str)
            if not (2 <= clusters <= 6):
                errors["customer_segment_clusters"] = "Number of customer segments must be between 2 and 6."
        except ValueError:
            errors["customer_segment_clusters"] = "Please enter an integer between 2 and 6."

        if not errors:
            settings_obj.forecast_confidence = confidence
            settings_obj.forecast_horizon_days = horizon
            settings_obj.forecast_cache_timeout = cache_timeout
            settings_obj.anomaly_contamination = contamination
            settings_obj.customer_segment_clusters = clusters
            settings_obj.email_alerts_anomaly = email_alerts
            settings_obj.stock_alerts_warehouse = stock_alerts
            settings_obj.updated_by = request.user
            settings_obj.save()

            from core.audit import log_action

            log_action(
                request=request,
                action="settings_updated",
                target_model="SystemSetting",
                target_id="1",
                details=(
                    f"Updated system configuration: Horizon={horizon}d, Contamination={contamination}, "
                    f"Confidence={confidence}, Clusters={clusters}, AnomalyAlerts={email_alerts}, StockAlerts={stock_alerts}."
                ),
            )

            messages.success(request, "System configuration parameters saved and applied successfully.")

    context = {
        "settings": settings_obj,
        "errors": errors,
    }
    return render(request, "analytics/system_settings.html", context)


@operations_manager_required
def accounts_receivable(request):
    """
    Accounts Receivable Dashboard:
    Tracks invoiced vs collected revenue, outstanding balances,
    and ageing buckets (0-30, 31-60, 61-90, 90+ days) per the Invoicing
    and Reporting Module specification.
    """
    today = timezone.now().date()

    invoices = Invoice.objects.select_related("order__customer").prefetch_related("payments").all()

    # Query filters
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    ageing_filter = request.GET.get("ageing", "").strip()
    account_type_filter = request.GET.get("account_type", "").strip()

    total_invoiced = Decimal("0.00")
    total_collected = Decimal("0.00")

    # Buckets: amounts and counts
    buckets = {
        "current": {"label": "0–30 Days (Current)", "amount": Decimal("0.00"), "count": 0, "badge": "success"},
        "month1": {"label": "31–60 Days", "amount": Decimal("0.00"), "count": 0, "badge": "info"},
        "month2": {"label": "61–90 Days", "amount": Decimal("0.00"), "count": 0, "badge": "warning"},
        "overdue": {"label": "90+ Days (Overdue)", "amount": Decimal("0.00"), "count": 0, "badge": "danger"},
    }

    invoice_list = []

    for inv in invoices:
        tot = Decimal(str(inv.total_amount))
        paid = inv.amount_paid
        bal = inv.balance
        age_days = (today - inv.issue_date).days

        total_invoiced += tot
        total_collected += paid

        # Determine ageing bucket
        if age_days <= 30:
            b_key = "current"
        elif age_days <= 60:
            b_key = "month1"
        elif age_days <= 90:
            b_key = "month2"
        else:
            b_key = "overdue"

        if bal > 0:
            buckets[b_key]["amount"] += bal
            buckets[b_key]["count"] += 1

        # Check filters for table display
        inv_data = {
            "invoice": inv,
            "order": inv.order,
            "customer": inv.order.customer,
            "total_amount": tot,
            "amount_paid": paid,
            "balance": bal,
            "age_days": max(0, age_days),
            "ageing_bucket": b_key,
            "status": inv.payment_status,
        }

        # Apply filters
        match = True
        if q:
            q_lower = q.lower()
            match = (
                q_lower in inv.order.customer.name.lower()
                or q in str(inv.invoice_id)
                or q in str(inv.order.order_id)
            )
        if match and status_filter:
            match = (inv.payment_status == status_filter)
        if match and ageing_filter:
            match = (b_key == ageing_filter)
        if match and account_type_filter:
            match = (inv.order.customer.account_type == account_type_filter)

        if match:
            invoice_list.append(inv_data)

    total_outstanding = max(Decimal("0.00"), total_invoiced - total_collected)
    collection_rate = round((total_collected / total_invoiced * 100), 1) if total_invoiced > 0 else 0.0

    # Calculate percentages for buckets
    for b in buckets.values():
        b["percent"] = round((b["amount"] / total_outstanding * 100), 1) if total_outstanding > 0 else 0.0

    context = {
        "total_invoiced": total_invoiced,
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "collection_rate": collection_rate,
        "buckets": buckets,
        "invoices": invoice_list,
        "q": q,
        "status_filter": status_filter,
        "ageing_filter": ageing_filter,
        "account_type_filter": account_type_filter,
        "account_types": ["KQ Internal Department", "Corporate Client", "Government Entity", "Distributor"],
    }
    return render(request, "analytics/accounts_receivable.html", context)


@operations_or_admin_required
def model_performance(request):
    """
    Model Retraining and Validation Performance Dashboard.
    Provides real-time model evaluation metrics (MAE, RMSE, MAPE, Silhouette, Contamination, Precision)
    and allows authorized managers and administrators to trigger retraining.
    """
    if request.method == "POST":
        target = request.POST.get("target_model", "all")
        from analytics.ml.pipeline import (
            train_and_persist_anomalies,
            train_and_persist_forecasting,
            train_and_persist_segmentation,
        )

        try:
            if target == "forecasting":
                train_and_persist_forecasting(user=request.user)
                messages.success(request, "Demand Forecasting (SARIMAX) retrained and validated successfully.")
            elif target == "segmentation":
                train_and_persist_segmentation(user=request.user)
                messages.success(request, "Customer Segmentation (K-Means) retrained and clustered successfully.")
            elif target == "anomaly":
                train_and_persist_anomalies(user=request.user)
                messages.success(request, "Order Anomaly Detection (Isolation Forest) retrained successfully.")
            else:
                train_and_persist_forecasting(user=request.user)
                train_and_persist_segmentation(user=request.user)
                train_and_persist_anomalies(user=request.user)
                messages.success(request, "All 3 machine learning models retrained and validated successfully.")

            log_action(
                user=request.user,
                action="retrain_ml_models",
                target_model="MLModelRun",
                details=f"Retrained ML model(s): {target}",
                request=request,
            )
        except Exception as e:
            messages.error(request, f"Error retraining models: {str(e)}")

        return redirect("analytics:model_performance")

    latest_forecasting = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.FORECASTING, status="completed"
    ).first()
    latest_segmentation = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.SEGMENTATION, status="completed"
    ).first()
    latest_anomaly = MLModelRun.objects.filter(
        model_type=MLModelRun.ModelType.ANOMALY, status="completed"
    ).first()

    history = MLModelRun.objects.select_related("trained_by").all()[:25]
    total_runs = MLModelRun.objects.count()
    total_anomalies_reviewed = OrderAnomalyRecord.objects.exclude(
        review_status=OrderAnomalyRecord.ReviewStatus.PENDING
    ).count()

    context = {
        "latest_forecasting": latest_forecasting,
        "latest_segmentation": latest_segmentation,
        "latest_anomaly": latest_anomaly,
        "history": history,
        "total_runs": total_runs,
        "total_anomalies_reviewed": total_anomalies_reviewed,
    }
    return render(request, "analytics/model_performance.html", context)


@operations_manager_required
def review_anomaly(request, anomaly_id):
    """
    Operations Manager Human-in-the-Loop review endpoint.
    Confirms or dismisses (false positive) flagged order anomalies.
    """
    anomaly = get_object_or_404(OrderAnomalyRecord, pk=anomaly_id)
    if request.method == "POST":
        status_val = request.POST.get("review_status")
        notes = request.POST.get("review_notes", "").strip()

        if status_val in [
            OrderAnomalyRecord.ReviewStatus.CONFIRMED,
            OrderAnomalyRecord.ReviewStatus.FALSE_POSITIVE,
        ]:
            anomaly.review_status = status_val
            anomaly.reviewed_by = request.user
            anomaly.reviewed_at = timezone.now()
            anomaly.review_notes = notes
            anomaly.save()

            log_action(
                user=request.user,
                action="review_order_anomaly",
                target_model="OrderAnomalyRecord",
                target_id=str(anomaly_id),
                details=f"Order KQ-{anomaly.order.order_id} reviewed as {anomaly.get_review_status_display()}: {notes}",
                request=request,
            )
            messages.success(
                request,
                f"Order KQ-{anomaly.order.order_id} marked as '{anomaly.get_review_status_display()}'.",
            )
        else:
            messages.error(request, "Invalid review status.")

    next_url = request.POST.get("next") or request.GET.get("next") or "analytics:dashboard"
    try:
        return redirect(next_url)
    except Exception:
        return redirect("analytics:dashboard")
