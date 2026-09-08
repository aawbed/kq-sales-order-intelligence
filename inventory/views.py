from django.shortcuts import get_object_or_404, render

from core.permissions import warehouse_officer_required
from inventory.models import Stock
from orders.models import Order


@warehouse_officer_required
def confirm_fulfilment(request):
    """Figure 3.7f: Warehouse Officer — Confirm Fulfilment."""
    pending_orders = Order.objects.filter(status=Order.Status.CONFIRMED)
    return render(request, "inventory/confirm_fulfilment.html", {"orders": pending_orders})


@warehouse_officer_required
def confirm_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    order.update_status(Order.Status.FULFILLED)
    return render(request, "inventory/confirm_fulfilment.html")


@warehouse_officer_required
def stock_levels(request):
    """Figure 3.7g: Warehouse Officer — Stock Levels."""
    stock = Stock.objects.select_related("product").all()
    return render(request, "inventory/stock_levels.html", {"stock": stock})


@warehouse_officer_required
def adjust_stock(request, stock_id):
    stock_item = get_object_or_404(Stock, pk=stock_id)
    return render(request, "inventory/stock_levels.html", {"stock_item": stock_item})
