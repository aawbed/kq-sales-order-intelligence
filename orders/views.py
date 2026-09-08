from django.shortcuts import get_object_or_404, render

from core.permissions import sales_agent_required
from orders.models import Customer, Order


@sales_agent_required
def create_order(request):
    """Figure 3.7b: Sales Agent — Create Order."""
    return render(request, "orders/create_order.html")


@sales_agent_required
def track_orders(request):
    """Figure 3.7c: Sales Agent — Track Orders."""
    orders = Order.objects.select_related("customer").all()
    return render(request, "orders/track_orders.html", {"orders": orders})


@sales_agent_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/order_detail.html", {"order": order})


@sales_agent_required
def customer_records(request):
    """Figure 3.7d: Sales Agent — Customer Records."""
    customers = Customer.objects.all()
    return render(request, "orders/customer_records.html", {"customers": customers})


@sales_agent_required
def customer_order_history(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    return render(request, "orders/customer_order_history.html", {"customer": customer})


@sales_agent_required
def generate_invoice(request, order_id):
    """Figure 3.7e: Sales Agent — Generate Invoice."""
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "orders/generate_invoice.html", {"order": order})
