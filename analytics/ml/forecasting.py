"""
Demand forecasting module.

Implements time-series regression (SARIMAX) for forecasting water
sales demand, as reviewed in Chapter 2 (Customer Sales Trend Analysis
/ Demand Forecasting literature) and referenced in the system
architecture diagram's ML Pipeline component.
"""


def forecast_demand(order_queryset, periods=30):
    """
    Fit a SARIMAX model on historical order volume and return a
    forecast for the given number of future periods.

    Placeholder implementation — to be built out with statsmodels'
    SARIMAX once historical order data is available.
    """
    raise NotImplementedError("SARIMAX forecasting model not yet implemented")
