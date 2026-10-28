"""
Anomaly detection module.

Implements Isolation Forest on standardized order and customer-relative
features to flag unusual order patterns (e.g. sudden volume spikes,
unusual order values relative to a customer's own baseline) for the
Operations Manager's ML Anomaly Detector panel on the Sales Dashboard.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def detect_anomalies(order_queryset, contamination=None, return_details=False):
    """
    Run Isolation Forest over order records and return a list
    of flagged anomalies with human-readable explanations and metadata.

    If return_details=True, returns (results, metrics, parameters).
    Otherwise returns results list.
    """
    feature_labels = ["Quantity", "Total Value", "Customer Frequency", "Customer Value Z-Score"]
    default_metrics = {"total_orders": 0, "anomalies_detected": 0, "contamination_rate": 0.05}
    default_params = {
        "algorithm": "Isolation Forest",
        "display_algorithm": "Isolation Forest (n_estimators=100, c=0.05)",
        "n_estimators": 100,
        "contamination": 0.05,
        "features": feature_labels,
    }

    try:
        if contamination is None:
            try:
                from analytics.models import SystemSetting

                contamination = SystemSetting.get_settings().anomaly_contamination
            except Exception:
                contamination = 0.05
        contamination = max(0.01, min(0.25, float(contamination)))
        default_params["contamination"] = contamination
        default_params["display_algorithm"] = f"Isolation Forest (n_estimators=100, c={contamination:g})"

        if not order_queryset.exists():
            return ([], default_metrics, default_params) if return_details else []

        data = []
        for order in order_queryset:
            items = list(order.items.all())
            if not items:
                continue
            quantity = sum(item.quantity for item in items)
            total_value = float(sum(item.quantity * item.unit_price for item in items))

            data.append({
                "order_id": order.order_id,
                "order_date": order.order_date.strftime("%Y-%m-%d"),
                "customer_id": order.customer_id,
                "customer_name": order.customer.name,
                "account_type": order.customer.account_type,
                "quantity": quantity,
                "total_value": total_value,
            })

        if len(data) < 5:
            return ([], default_metrics, default_params) if return_details else []

        df = pd.DataFrame(data)

        # Total customer order frequency across evaluated dataset (avoids penalizing earliest orders)
        cust_stats = df.groupby("customer_id")["total_value"].agg(["count", "mean", "std"]).reset_index()
        cust_stats.rename(
            columns={"count": "freq", "mean": "cust_mean_val", "std": "cust_std_val"},
            inplace=True,
        )
        df = df.merge(cust_stats, on="customer_id", how="left")
        df["cust_std_val"] = df["cust_std_val"].fillna(0.0)
        df["customer_zscore"] = np.where(
            df["cust_std_val"] > 0,
            (df["total_value"] - df["cust_mean_val"]) / df["cust_std_val"],
            0.0,
        )

        feature_cols = ["quantity", "total_value", "freq", "customer_zscore"]
        scaled_features = StandardScaler().fit_transform(df[feature_cols])

        iso = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
        )
        df["is_anomaly"] = iso.fit_predict(scaled_features)
        df["anomaly_score"] = iso.decision_function(scaled_features)

        # Generate clear, human-readable explanations based on global and customer-relative deviations
        mean_qty = float(df["quantity"].mean())
        mean_val = float(df["total_value"].mean())

        def explain_anomaly(row):
            reasons = []
            if row["quantity"] > mean_qty * 2.2:
                reasons.append(f"Volume spike ({int(row['quantity']):,} units vs avg {mean_qty:.0f})")
            elif row["quantity"] < mean_qty * 0.15 and row["freq"] > 5:
                reasons.append(f"Unusually small order ({int(row['quantity'])} units)")
            if row["total_value"] > mean_val * 2.2:
                reasons.append(f"High transaction value (KSh {row['total_value']:,.2f})")
            if abs(row["customer_zscore"]) >= 2.0:
                direction = "above" if row["customer_zscore"] > 0 else "below"
                reasons.append(
                    f"Order value {abs(row['customer_zscore']):.1f} SD {direction} account average"
                )
            if row["freq"] <= 1 and row["total_value"] > mean_val * 1.5:
                reasons.append("Single-order customer high-value booking")
            if not reasons:
                reasons.append("Multivariate outlier across volume, value & account baseline")
            return "; ".join(reasons)

        df["explanation"] = df.apply(explain_anomaly, axis=1)

        anomalies = df[df["is_anomaly"] == -1].copy()
        anomalies["is_anomaly"] = True
        anomalies["anomaly_score"] = anomalies["anomaly_score"].astype(float)
        anomalies.sort_values("anomaly_score", ascending=True, inplace=True)

        anomaly_records = anomalies[[
            "order_id",
            "order_date",
            "customer_name",
            "account_type",
            "quantity",
            "total_value",
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
