"""
Demand forecasting module.

Implements time-series regression (SARIMAX) for forecasting water
sales demand, as reviewed in Chapter 2 (Customer Sales Trend Analysis
/ Demand Forecasting literature) and referenced in the system
architecture diagram's ML Pipeline component.
"""


import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

def forecast_demand(order_queryset, periods=None):
    """
    Fit a SARIMAX model on historical order volume and return a
    forecast for the given number of future periods.
    """
    try:
        if periods is None:
            try:
                from analytics.models import SystemSetting
                periods = SystemSetting.get_settings().forecast_horizon_days
            except Exception:
                periods = 30
        periods = max(7, min(90, int(periods)))

        from orders.models import OrderItem
        items = OrderItem.objects.filter(order__in=order_queryset).select_related('order')
        if not items.exists():
            return []
        
        data = []
        for item in items:
            data.append({'date': item.order.order_date.date(), 'quantity': item.quantity})
            
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.groupby('date')['quantity'].sum().reset_index()
        df.set_index('date', inplace=True)
        df = df.asfreq('D', fill_value=0)
        
        if len(df) < 2:
            return []

        if len(df) > 10:
            model = SARIMAX(df['quantity'], order=(1, 1, 1), seasonal_order=(0, 0, 0, 0))
            fit_model = model.fit(disp=False)
            forecast = fit_model.forecast(steps=periods)
        else:
            model = SimpleExpSmoothing(df['quantity'])
            fit_model = model.fit()
            forecast = fit_model.forecast(steps=periods)
            
        results = []
        for date, qty in forecast.items():
            results.append({'date': date.strftime('%Y-%m-%d'), 'predicted_quantity': max(0, float(qty))})
        return results
    except Exception as e:
        return []
