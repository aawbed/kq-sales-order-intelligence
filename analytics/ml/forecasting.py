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

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX


def forecast_demand(order_queryset, periods=None, return_details=False):
    """
    Fit a SARIMAX model on historical order volume and return a
    forecast for the given number of future periods.

    If return_details=True, returns (results, metrics, parameters).
    Otherwise returns results list.
    """
    default_metrics = {"mae": 0.0, "rmse": 0.0, "mape": 0.0}
    default_params = {"algorithm": "SARIMAX", "order": [1, 1, 1], "periods": 30}

    try:
        if periods is None:
            try:
                from analytics.models import SystemSetting
                periods = SystemSetting.get_settings().forecast_horizon_days
            except Exception:
                periods = 30
        periods = max(7, min(90, int(periods)))
        default_params["periods"] = periods

        from orders.models import OrderItem

        items = OrderItem.objects.filter(order__in=order_queryset).select_related("order")
        if not items.exists():
            return ([], default_metrics, default_params) if return_details else []

        data = []
        for item in items:
            data.append({"date": item.order.order_date.date(), "quantity": item.quantity})

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.groupby("date")["quantity"].sum().reset_index()
        df.set_index("date", inplace=True)
        df = df.asfreq("D", fill_value=0)

        if len(df) < 2:
            return ([], default_metrics, default_params) if return_details else []

        mae, rmse, mape = 0.0, 0.0, 0.0
        results = []

        if len(df) > 10:
            default_params["algorithm"] = "SARIMAX"
            # Train / validation split for model evaluation
            if len(df) >= 20:
                test_size = min(14, int(len(df) * 0.2))
                train_series = df["quantity"].iloc[:-test_size]
                test_series = df["quantity"].iloc[-test_size:]
                try:
                    eval_model = SARIMAX(train_series, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0)).fit(disp=False)
                    eval_pred = eval_model.forecast(steps=test_size)
                    errors = test_series.values - eval_pred.values
                    mae = float(np.mean(np.abs(errors)))
                    rmse = float(np.sqrt(np.mean(errors**2)))
                    denom = np.where(test_series.values == 0, 1.0, test_series.values)
                    mape = float(np.mean(np.abs(errors) / denom) * 100)
                except Exception:
                    pass

            full_model = SARIMAX(df["quantity"], order=(1, 1, 1), seasonal_order=(0, 0, 0, 0))
            fit_model = full_model.fit(disp=False)
            forecast_res = fit_model.get_forecast(steps=periods)
            predicted_means = forecast_res.predicted_mean
            conf_int = forecast_res.conf_int(alpha=0.05)

            # Fallback metrics if train/test split failed
            if mae == 0.0:
                fitted = fit_model.fittedvalues
                residuals = df["quantity"].values - fitted.values
                mae = float(np.mean(np.abs(residuals)))
                rmse = float(np.sqrt(np.mean(residuals**2)))
                denom = np.where(df["quantity"].values == 0, 1.0, df["quantity"].values)
                mape = float(np.mean(np.abs(residuals) / denom) * 100)

            for date, qty in predicted_means.items():
                lower = float(conf_int.loc[date].iloc[0]) if date in conf_int.index else float(qty) * 0.8
                upper = float(conf_int.loc[date].iloc[1]) if date in conf_int.index else float(qty) * 1.2
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_quantity": max(0.0, round(float(qty), 1)),
                    "confidence_lower": max(0.0, round(lower, 1)),
                    "confidence_upper": max(0.0, round(upper, 1)),
                })
        else:
            default_params["algorithm"] = "Simple Exponential Smoothing"
            model = SimpleExpSmoothing(df["quantity"])
            fit_model = model.fit()
            forecast = fit_model.forecast(steps=periods)
            fitted = fit_model.fittedvalues
            residuals = df["quantity"].values - fitted.values
            mae = float(np.mean(np.abs(residuals)))
            rmse = float(np.sqrt(np.mean(residuals**2)))
            denom = np.where(df["quantity"].values == 0, 1.0, df["quantity"].values)
            mape = float(np.mean(np.abs(residuals) / denom) * 100)

            for date, qty in forecast.items():
                val = max(0.0, round(float(qty), 1))
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_quantity": val,
                    "confidence_lower": max(0.0, round(val * 0.85, 1)),
                    "confidence_upper": round(val * 1.15, 1),
                })

        metrics = {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "mape": round(min(100.0, mape), 2),
            "sample_days": len(df),
        }

        if return_details:
            return results, metrics, default_params
        return results

    except Exception:
        if return_details:
            return [], default_metrics, default_params
        return []
