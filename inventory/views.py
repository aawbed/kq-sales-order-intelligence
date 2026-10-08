from django.contrib import messages
from django.db import models, transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import warehouse_officer_required
from inventory.forms import ProductForm, StockAdjustmentForm
from inventory.models import Product, Stock
from orders.models import Order


@warehouse_officer_required
def confirm_fulfilment(request):
    """
    Figure 3.7f: Warehouse Officer — Confirm Fulfilment.
    Orders are prioritised with Urgent bookings first, followed by High and Normal,
    then chronologically by booking date.
    """
    priority_order = models.Case(
        models.When(priority=Order.Priority.URGENT, then=models.Value(1)),
        models.When(priority=Order.Priority.HIGH, then=models.Value(2)),
        models.When(priority=Order.Priority.NORMAL, then=models.Value(3)),
        default=models.Value(4),
        output_field=models.IntegerField(),
    )
    pending_orders = (
        Order.objects.filter(status=Order.Status.CONFIRMED)
        .annotate(priority_rank=priority_order)
        .order_by("priority_rank", "-order_date")
        .select_related("customer")
        .prefetch_related("items__product")
    )
    return render(request, "inventory/confirm_fulfilment.html", {"orders": pending_orders})


@warehouse_officer_required
def confirm_order(request, order_id):
    """Mark order as fulfilled AND deduct stock for each item."""
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product__stock"),
        pk=order_id,
    )

    if order.status != Order.Status.CONFIRMED:
        messages.warning(request, f"Order KQ-{order.order_id} is not in 'Confirmed' status.")
        return redirect("inventory:confirm_fulfilment")

    dispatch_notes = request.POST.get("dispatch_notes", "").strip()

    with transaction.atomic():
        for item in order.items.all():
            try:
                stock = item.product.stock
                stock.update_level(-item.quantity, reason=f"Fulfilled Order KQ-{order.order_id}")
            except Stock.DoesNotExist:
                pass  # Product has no stock record — skip

        order.status = Order.Status.FULFILLED
        if dispatch_notes:
            order.fulfillment_notes = dispatch_notes
            order.save(update_fields=["status", "fulfillment_notes"])
        else:
            order.save(update_fields=["status"])

        from core.audit import log_action

        note_detail = f" (Notes: '{dispatch_notes}')" if dispatch_notes else ""
        log_action(
            request=request,
            action="order_status_changed",
            target_model="Order",
            target_id=f"KQ-{order.order_id}",
            details=f"Warehouse Officer confirmed fulfilment{note_detail}; status changed to Fulfilled. Stock deducted for {order.items.count()} item(s).",
        )

    messages.success(request, f"Order KQ-{order.order_id} fulfilled. Stock has been deducted.")
    return redirect("inventory:confirm_fulfilment")


@warehouse_officer_required
def stock_levels(request):
    """Figure 3.7g: Warehouse Officer — Stock Levels."""
    if request.method == "POST" and "add_product" in request.POST:
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            Stock.objects.create(product=product, quantity_on_hand=0, reorder_level=0)
            messages.success(request, f"{product.name} added to inventory.")
            return redirect("inventory:stock_levels")
    else:
        form = ProductForm()

    stock = Stock.objects.select_related("product").all()
    return render(request, "inventory/stock_levels.html", {"stock": stock, "form": form})


@warehouse_officer_required
def adjust_stock(request, stock_id):
    stock_item = get_object_or_404(Stock, pk=stock_id)
    if request.method == "POST":
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            offset = form.cleaned_data["offset"]
            reason = form.cleaned_data["reason"]
            stock_item.update_level(offset, reason=reason)

            from core.audit import log_action

            log_action(
                request=request,
                action="stock_adjusted",
                target_model="Stock",
                target_id=f"{stock_item.product.name}",
                details=f"Manual inventory adjustment: {offset:+d} units ({reason}). New balance: {stock_item.quantity_on_hand} units.",
            )

            messages.success(request, f"{stock_item.product.name} adjusted by {offset:+d} units.")
    return redirect("inventory:stock_levels")