from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    # Figure 3.7f: Confirm Fulfilment
    path("fulfilment/", views.confirm_fulfilment, name="confirm_fulfilment"),
    path("fulfilment/<int:order_id>/confirm/", views.confirm_order, name="confirm_order"),
    # Figure 3.7g: Stock Levels
    path("stock/", views.stock_levels, name="stock_levels"),
    path("stock/<int:stock_id>/adjust/", views.adjust_stock, name="adjust_stock"),
]
