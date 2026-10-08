from decimal import Decimal

from django.contrib import messages
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import sales_agent_required, sales_or_operations_required
from orders.forms import CustomerForm, OrderForm, OrderItemFormSet, PaymentForm
from orders.invoice_pdf import generate_invoice_pdf
from orders.models import Customer, Invoice, Order, Payment


@sales_agent_required
def create_order(request):
    """Figure 3.7b: Sales Agent — Create Order (fully functional)."""
    if request.method == "POST":
        order_form = OrderForm(request.POST)
        if order_form.is_valid():
            with transaction.atomic():
                order = order_form.save(commit=False)
                order.created_by = request.user
                order.save()

                item_formset = OrderItemFormSet(request.POST, instance=order)
                if item_formset.is_valid():
                    items = item_formset.save(commit=False)
                    for item in items:
                        item.unit_price = item.product.unit_price
                        item.save()
                    # Delete any items marked for deletion
                    for obj in item_formset.deleted_objects:
                        obj.delete()

                    # Evaluate order for ML anomaly patterns
                    try:
                        from core.alerts import check_and_alert_anomaly

                        check_and_alert_anomaly(order)
                    except Exception:
                        pass

                    # Audit trail
                    from core.audit import log_action
                    log_action(
                        request=request,
                        action="order_created",
                        target_model="Order",
                        target_id=f"KQ-{order.order_id}",
                        details=f"Created order for {order.customer.name} (Priority: {order.get_priority_display()}) with {len(items)} line item(s).",
                    )

                    messages.success(
                        request,
                        f"Order KQ-{order.order_id} created successfully "
                        f"with {len(items)} item(s).",
                    )
                    return redirect("orders:order_detail", order_id=order.order_id)
                else:
                    # If items are invalid, delete the partially created order
                    order.delete()
                    messages.error(request, "Please add at least one valid item.")
        else:
            item_formset = OrderItemFormSet(request.POST)
    else:
        order_form = OrderForm()
        item_formset = OrderItemFormSet()

    return render(
        request,
        "orders/create_order.html",
        {"order_form": order_form, "item_formset": item_formset},
    )


@sales_agent_required
def track_orders(request):
    """Figure 3.7c: Sales Agent — Track Orders."""
    query = request.GET.get("q", "").strip()
    orders = Order.objects.select_related("customer").all()
    if query:
        orders = orders.filter(
            models.Q(customer__name__icontains=query)
            | models.Q(order_id__icontains=query)
        )
    return render(request, "orders/track_orders.html", {"orders": orders, "query": query})


@sales_agent_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related("items__product"),
        pk=order_id,
    )
    return render(request, "orders/order_detail.html", {"order": order})


@sales_agent_required
def confirm_order(request, order_id):
    """Sales Agent confirms a pending order — moves it to 'confirmed' status."""
    order = get_object_or_404(Order, pk=order_id)
    if order.status == Order.Status.PENDING:
        order.update_status(Order.Status.CONFIRMED)
        from core.audit import log_action

        log_action(
            request=request,
            action="order_status_changed",
            target_model="Order",
            target_id=f"KQ-{order.order_id}",
            details="Sales Agent confirmed order; status changed from Pending to Confirmed.",
        )
        messages.success(request, f"Order KQ-{order.order_id} confirmed.")
    else:
        messages.warning(request, f"Order KQ-{order.order_id} is already {order.get_status_display()}.")
    return redirect("orders:order_detail", order_id=order.order_id)


@sales_agent_required
def customer_records(request):
    """Figure 3.7d: Sales Agent — Customer Records."""
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer added successfully.")
            return redirect("orders:customer_records")
    else:
        form = CustomerForm()

    query = request.GET.get("q", "").strip()
    customers = Customer.objects.all()
    if query:
        customers = customers.filter(
            models.Q(name__icontains=query)
            | models.Q(contact_info__icontains=query)
            | models.Q(account_type__icontains=query)
        )

    return render(
        request,
        "orders/customer_records.html",
        {"customers": customers, "form": form, "query": query},
    )


@sales_agent_required
def customer_order_history(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    orders = customer.orders.all()
    return render(
        request,
        "orders/customer_order_history.html",
        {"customer": customer, "orders": orders},
    )


@sales_or_operations_required
def generate_invoice(request, order_id):
    """Figure 3.7e: Generate Invoice & Payment Statement."""
    order = get_object_or_404(
        Order.objects.select_related("customer").prefetch_related("items__product"),
        pk=order_id,
    )

    existing_invoice = getattr(order, "invoice", None)

    # If POST and no invoice exists, generate it
    if request.method == "POST" and not existing_invoice:
        invoice = Invoice.generate(order)
        messages.success(request, f"Invoice #{invoice.invoice_id} generated successfully.")
        return redirect("orders:generate_invoice", order_id=order.order_id)

    items = order.items.all()
    if existing_invoice:
        subtotal = existing_invoice.subtotal
        vat = existing_invoice.vat_amount
        total = existing_invoice.total_amount
        payments = existing_invoice.payments.select_related("recorded_by").all()
        payment_form = PaymentForm(invoice=existing_invoice)
    else:
        subtotal = sum(item.line_total for item in items)
        vat = round(Decimal(str(subtotal)) * Decimal("0.16"), 2)
        total = Decimal(str(subtotal)) + vat
        payments = []
        payment_form = None

    return render(
        request,
        "orders/generate_invoice.html",
        {
            "order": order,
            "items": items,
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
            "existing_invoice": existing_invoice,
            "payments": payments,
            "payment_form": payment_form,
        },
    )


@sales_or_operations_required
def record_payment(request, order_id):
    """Record a payment against an order's invoice."""
    order = get_object_or_404(Order, pk=order_id)
    if not hasattr(order, "invoice"):
        messages.error(request, "Cannot record payment: no invoice has been generated for this order.")
        return redirect("orders:order_detail", order_id=order.order_id)

    invoice = order.invoice
    if request.method == "POST":
        form = PaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.recorded_by = request.user
            payment.save()

            from core.audit import log_action

            log_action(
                request=request,
                action="payment_recorded",
                target_model="Payment",
                target_id=f"PAY-{payment.payment_id}",
                details=(
                    f"Recorded payment of KSh {payment.amount:,.2f} via {payment.get_method_display()} "
                    f"(Ref: {payment.reference or 'N/A'}) for Invoice #{invoice.invoice_id} "
                    f"(Order KQ-{order.order_id}). New invoice balance: KSh {invoice.balance:,.2f}."
                ),
            )

            messages.success(
                request,
                f"Payment of KSh {payment.amount:,.2f} recorded via {payment.get_method_display()} "
                f"(Ref: {payment.reference or 'N/A'}). Invoice balance: KSh {invoice.balance:,.2f}.",
            )
            return redirect("orders:generate_invoice", order_id=order.order_id)
        else:
            # Re-render invoice page with validation errors
            items = order.items.all()
            return render(
                request,
                "orders/generate_invoice.html",
                {
                    "order": order,
                    "items": items,
                    "subtotal": invoice.subtotal,
                    "vat": invoice.vat_amount,
                    "total": invoice.total_amount,
                    "existing_invoice": invoice,
                    "payments": invoice.payments.select_related("recorded_by").all(),
                    "payment_form": form,
                },
            )

    return redirect("orders:generate_invoice", order_id=order.order_id)


@sales_or_operations_required
def export_invoice_pdf(request, order_id):
    """Export order tax invoice as a branded PDF document."""
    order = get_object_or_404(
        Order.objects.select_related("customer", "invoice").prefetch_related("items__product"),
        pk=order_id,
    )
    pdf_bytes = generate_invoice_pdf(order)
    inv_id = order.invoice.invoice_id if hasattr(order, "invoice") else order.order_id
    filename = f"KQ_Invoice_INV-{inv_id}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
