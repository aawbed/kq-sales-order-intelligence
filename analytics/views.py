import json
from datetime import timedelta

from django.db import models
from django.shortcuts import render
from django.utils import timezone

from decimal import Decimal

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
    """Figure 3.7i: Operations Manager — Generate Reports."""
    return render(request, "analytics/generate_reports.html")


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
