from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    # Figure 3.7b: Create Order
    path("create/", views.create_order, name="create_order"),
    # Figure 3.7c: Track Orders
    path("", views.track_orders, name="track_orders"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    # Figure 3.7d: Customer Records
    path("customers/", views.customer_records, name="customer_records"),
    path("customers/<int:customer_id>/history/", views.customer_order_history, name="customer_order_history"),
    # Figure 3.7e: Generate Invoice
    path("<int:order_id>/invoice/", views.generate_invoice, name="generate_invoice"),
]
