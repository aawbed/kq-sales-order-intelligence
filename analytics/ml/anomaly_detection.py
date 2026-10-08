"""
Anomaly detection module.

Implements Isolation Forest to flag unusual order patterns (e.g. sudden
demand spikes, dormant-account reactivation) for the Operations
Manager's ML Anomaly Detector panel on the Sales Dashboard.
"""


import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_anomalies(order_queryset, contamination=None, return_details=False):
    """
    Run Isolation Forest over recent order records and return a list
    of flagged anomalies with a short human-readable description.

    If return_details=True, returns (results, metrics, parameters).
    Otherwise returns results list.
    """
    default_metrics = {"total_orders": 0, "anomalies_detected": 0, "contamination_rate": 0.05}
    default_params = {"algorithm": "Isolation Forest", "contamination": 0.05}

    try:
        if contamination is None:
            try:
                from analytics.models import SystemSetting
                contamination = SystemSetting.get_settings().anomaly_contamination
            except Exception:
                contamination = 0.05
        contamination = max(0.01, min(0.25, float(contamination)))
        default_params["contamination"] = contamination

        if not order_queryset.exists():
            return ([], default_metrics, default_params) if return_details else []

        data = []
        for order in order_queryset:
            items = order.items.all()
            if not items.exists():
                continue
            quantity = sum(item.quantity for item in items)
            total_value = sum(item.quantity * item.unit_price for item in items)
            freq = order.customer.orders.count()

            data.append({
                "order_id": order.order_id,
                "customer_name": order.customer.name,
                "quantity": quantity,
                "total_value": float(total_value),
                "freq": freq,
            })

        if len(data) < 5:
            return ([], default_metrics, default_params) if return_details else []

        df = pd.DataFrame(data)
        features = df[["quantity", "total_value", "freq"]]

        iso = IsolationForest(contamination=contamination, random_state=42)
        df["is_anomaly"] = iso.fit_predict(features)
        df["anomaly_score"] = iso.decision_function(features)

        # Generate human-readable explanations based on feature deviations
        mean_qty = df["quantity"].mean()
        mean_val = df["total_value"].mean()

        def explain_anomaly(row):
            reasons = []
            if row["quantity"] > mean_qty * 2.5:
                reasons.append(f"Volume spike ({row['quantity']} units vs avg {mean_qty:.0f})")
            elif row["quantity"] < mean_qty * 0.1 and row["freq"] > 5:
                reasons.append(f"Unusually tiny order ({row['quantity']} units)")
            if row["total_value"] > mean_val * 2.5:
                reasons.append(f"High transaction value (KES {row['total_value']:,.2f})")
            if row["freq"] <= 1 and row["total_value"] > mean_val:
                reasons.append("First-time customer large order")
            if not reasons:
                reasons.append("Outlier combination in order volume & customer history")
            return "; ".join(reasons)

        df["explanation"] = df.apply(explain_anomaly, axis=1)

        anomalies = df[df["is_anomaly"] == -1].copy()
        anomalies["is_anomaly"] = True
        anomalies["anomaly_score"] = anomalies["anomaly_score"].astype(float)

        anomaly_records = anomalies[[
            "order_id",
            "customer_name",
            "anomaly_score",
            "is_anomaly",
            "explanation",
        ]].to_dict("records")

        metrics = {
            "total_orders": len(df),
            "anomalies_detected": len(anomalies),
            "contamination_rate": round(len(anomalies) / max(1, len(df)), 4),
            "min_score": round(float(df["anomaly_score"].min()), 3),
            "mean_score": round(float(df["anomaly_score"].mean()), 3),
        }

        if return_details:
            return anomaly_records, metrics, default_params
        return anomaly_records
    except Exception:
        if return_details:
            return [], default_metrics, default_params
        return []
