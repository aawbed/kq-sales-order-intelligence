import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.db import models
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from analytics.models import Report
from analytics.report_pdf import generate_report_pdf
from core.permissions import operations_manager_required, system_administrator_required
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

    # --- ML Outputs (safely wrapped) ---
    forecast_data = []
    anomaly_data = []
    segmentation_data = []

    all_orders = Order.objects.select_related("customer").prefetch_related("items__product").all()

    try:
        from analytics.ml.forecasting import forecast_demand
        forecast_data = forecast_demand(all_orders)
    except Exception:
        pass

    try:
        from analytics.ml.anomaly_detection import detect_anomalies
        anomaly_data = detect_anomalies(all_orders)
    except Exception:
        pass

    try:
        from analytics.ml.customer_segmentation import segment_customers
        segmentation_data = segment_customers(Customer.objects.prefetch_related("orders__items").all())
    except Exception:
        pass

    # Prepare forecast chart data for JS
    forecast_labels = json.dumps([row.get("date", "") for row in forecast_data[:30]])
    forecast_values = json.dumps([round(float(row.get("predicted_quantity", 0)), 1) for row in forecast_data[:30]])

    context = {
        "recent_revenue": round(recent_revenue, 2),
        "weekly_orders": weekly_orders,
        "low_stock_count": low_stock_count,
        "active_customers": active_customers,
        "forecast_labels": forecast_labels,
        "forecast_values": forecast_values,
        "anomalies": anomaly_data[:10],
        "segments": segmentation_data,
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
    """Figure 3.7k: System Administrator — System Settings."""
    return render(request, "analytics/system_settings.html")


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
