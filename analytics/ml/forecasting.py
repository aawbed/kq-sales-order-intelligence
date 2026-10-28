"""
Demand forecasting module.

Implements seasonal time-series state-space forecasting — SARIMAX(1,1,1)(1,0,1,7) —
for water sales demand, as reviewed in Chapter 2 (Customer Sales Trend Analysis
/ Demand Forecasting literature) and referenced in the system architecture
diagram's ML Pipeline component.
"""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX


def _compute_error_metrics(actuals, predictions):
    """
    Compute daily MAE and RMSE plus 7-day rolling replenishment WMAPE and sMAPE
    between actual and predicted arrays without artificial clamping.
    """
    actuals_arr = np.asarray(actuals, dtype=float)
    preds_arr = np.maximum(0.0, np.asarray(predictions, dtype=float))
    errors = actuals_arr - preds_arr

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    # For intermittent B2B demand (where individual calendar days frequently have 0 orders),
    # evaluate percentage accuracy over 7-day replenishment windows when >=7 days are available.
    if len(actuals_arr) >= 7:
        kernel = np.ones(7, dtype=float)
        roll_act = np.convolve(actuals_arr, kernel, mode="valid")
        roll_pred = np.convolve(preds_arr, kernel, mode="valid")
        total_roll = float(np.sum(roll_act))
        wmape = float(np.sum(np.abs(roll_act - roll_pred)) / total_roll * 100.0) if total_roll > 0 else 0.0
        denom = np.abs(roll_act) + np.abs(roll_pred)
        valid = denom > 0
        smape = float(np.mean(2.0 * np.abs(roll_act[valid] - roll_pred[valid]) / denom[valid]) * 100.0) if np.any(valid) else 0.0
    else:
        total_actual = float(np.sum(actuals_arr))
        wmape = float(np.sum(np.abs(errors)) / total_actual * 100.0) if total_actual > 0 else 0.0
        denom = np.abs(actuals_arr) + np.abs(preds_arr)
        valid = denom > 0
        smape = float(np.mean(2.0 * np.abs(errors[valid]) / denom[valid]) * 100.0) if np.any(valid) else 0.0

    return mae, rmse, wmape, smape


def forecast_demand(order_queryset, periods=None, confidence=None, return_details=False):
    """
    Fit a seasonal SARIMAX model on historical daily order volume and return a
    forecast for the given number of future periods.

    If return_details=True, returns (results, metrics, parameters).
    Otherwise returns results list.
    """
    default_metrics = {"mae": 0.0, "rmse": 0.0, "mape": 0.0, "smape": 0.0}
    default_params = {
        "algorithm": "SARIMAX",
        "display_algorithm": "SARIMAX (1,1,1)(1,0,1,7)",
        "order": [1, 1, 1],
        "seasonal_order": [1, 0, 1, 7],
        "periods": 30,
        "confidence": 0.85,
    }

    try:
        try:
            from analytics.models import SystemSetting

            cfg = SystemSetting.get_settings()
            if periods is None:
                periods = cfg.forecast_horizon_days
            if confidence is None:
                confidence = cfg.forecast_confidence
        except Exception:
            if periods is None:
                periods = 30
            if confidence is None:
                confidence = 0.85

        periods = max(7, min(90, int(periods)))
        confidence = max(0.50, min(0.99, float(confidence)))
        alpha = round(1.0 - confidence, 4)
        default_params["periods"] = periods
        default_params["confidence"] = round(confidence, 2)

        from orders.models import OrderItem

        items = OrderItem.objects.filter(order__in=order_queryset).select_related("order")
        if not items.exists():
            return ([], default_metrics, default_params) if return_details else []

        data = [
            {"date": item.order.order_date.date(), "quantity": item.quantity}
            for item in items
        ]

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.groupby("date")["quantity"].sum().reset_index()
        df.set_index("date", inplace=True)
        df = df.asfreq("D", fill_value=0)

        if len(df) < 2:
            return ([], default_metrics, default_params) if return_details else []

        mae, rmse, wmape, smape = 0.0, 0.0, 0.0, 0.0
        naive_mae = None
        results = []

        # Winsorize extreme anomalous single-day spikes (>95th percentile of active days)
        # so Isolation Forest order spikes do not distort baseline demand forecasting.
        raw_series = df["quantity"].astype(float)
        nonzero_vals = raw_series[raw_series > 0]
        if len(nonzero_vals) >= 10:
            upper_cap = float(np.percentile(nonzero_vals, 95))
            clean_series = raw_series.clip(upper=upper_cap)
        else:
            clean_series = raw_series

        if len(df) > 10:
            default_params["algorithm"] = "SARIMAX"
            seasonal_order = (1, 0, 1, 7) if len(df) >= 21 else (0, 0, 0, 0)
            default_params["seasonal_order"] = list(seasonal_order)
            default_params["display_algorithm"] = (
                "SARIMAX (1,1,1)(1,0,1,7)"
                if seasonal_order[3] > 0
                else "SARIMAX (1,1,1)"
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                # Out-of-sample holdout validation split
                if len(clean_series) >= 20:
                    test_size = min(28, max(7, int(len(clean_series) * 0.15)))
                    train_series = clean_series.iloc[:-test_size]
                    test_series = clean_series.iloc[-test_size:]
                    eval_seasonal = (1, 0, 1, 7) if len(train_series) >= 21 else (0, 0, 0, 0)
                    try:
                        eval_model = SARIMAX(
                            train_series,
                            order=(1, 1, 1),
                            seasonal_order=eval_seasonal,
                            enforce_stationarity=False,
                            enforce_invertibility=False,
                        ).fit(disp=False)
                        eval_pred = np.maximum(0.0, eval_model.forecast(steps=test_size).values)
                        mae, rmse, wmape, smape = _compute_error_metrics(
                            test_series.values, eval_pred
                        )
                        if len(train_series) >= 7:
                            # 7-day seasonal naive baseline (same weekday from final training week)
                            last_week = train_series.iloc[-7:].values
                            naive_preds = np.resize(last_week, test_size)
                            naive_mae = float(np.mean(np.abs(test_series.values - naive_preds)))
                    except Exception:
                        pass

                try:
                    full_model = SARIMAX(
                        clean_series,
                        order=(1, 1, 1),
                        seasonal_order=seasonal_order,
                        enforce_stationarity=False,
                        enforce_invertibility=False,
                    )
                    fit_model = full_model.fit(disp=False)
                except Exception:
                    default_params["seasonal_order"] = [0, 0, 0, 0]
                    default_params["display_algorithm"] = "SARIMAX (1,1,1)"
                    full_model = SARIMAX(
                        clean_series,
                        order=(1, 1, 1),
                        seasonal_order=(0, 0, 0, 0),
                    )
                    fit_model = full_model.fit(disp=False)

                forecast_res = fit_model.get_forecast(steps=periods)
                predicted_means = forecast_res.predicted_mean
                conf_int = forecast_res.conf_int(alpha=alpha)

            # Fallback to in-sample residuals only if holdout split could not run
            if mae == 0.0 and len(clean_series) > 2:
                fitted = np.maximum(0.0, fit_model.fittedvalues.values)
                mae, rmse, wmape, smape = _compute_error_metrics(clean_series.values, fitted)

            for date, qty in predicted_means.items():
                pred_val = max(0.0, float(qty))
                lower = float(conf_int.loc[date].iloc[0]) if date in conf_int.index else pred_val * 0.8
                upper = float(conf_int.loc[date].iloc[1]) if date in conf_int.index else pred_val * 1.2
                results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_quantity": round(pred_val, 1),
                    "confidence_lower": max(0.0, round(lower, 1)),
                    "confidence_upper": max(round(pred_val, 1), round(upper, 1)),
                })
        else:
            default_params["algorithm"] = "Simple Exponential Smoothing"
            default_params["display_algorithm"] = "Simple Exponential Smoothing"
            default_params["seasonal_order"] = [0, 0, 0, 0]
            model = SimpleExpSmoothing(clean_series)
            fit_model = model.fit()
            forecast = fit_model.forecast(steps=periods)
            fitted = fit_model.fittedvalues.values
            mae, rmse, wmape, smape = _compute_error_metrics(clean_series.values, fitted)

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
            "mape": round(wmape, 2),
            "smape": round(smape, 2),
            "sample_days": len(df),
        }
        if naive_mae and naive_mae > 0:
            metrics["naive_mae"] = round(naive_mae, 2)
            metrics["skill_vs_naive_pct"] = round((1.0 - mae / naive_mae) * 100.0, 1)

        if return_details:
            return results, metrics, default_params
        return results

    except Exception:
        if return_details:
            return [], default_metrics, default_params
        return []
