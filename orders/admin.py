from django.contrib import admin

from .models import Customer, Invoice, Order, OrderItem, Payment

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "name", "account_type", "contact_info")
    search_fields = ("name", "contact_info", "account_type")
    list_filter = ("account_type",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "customer", "status", "order_date", "created_by")
    list_filter = ("status", "order_date")
    search_fields = ("order_id", "customer__name")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order_item_id", "order", "product", "quantity", "unit_price", "line_total")
    search_fields = ("order__order_id", "product__name")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("payment_id", "payment_date", "recorded_by")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_id", "order", "issue_date", "total_amount", "amount_paid", "balance", "payment_status")
    list_filter = ("issue_date",)
    search_fields = ("invoice_id", "order__order_id", "order__customer__name")
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_id", "invoice", "payment_date", "method", "reference", "amount", "recorded_by")
    list_filter = ("method", "payment_date")
    search_fields = ("payment_id", "reference", "invoice__invoice_id", "invoice__order__customer__name")
