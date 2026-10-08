"""
Customer segmentation module.

Implements RFM (Recency, Frequency, Monetary)-based k-means clustering
to segment customers by purchasing behaviour, as reviewed in Chapter 2
(Customer Sales Trend Analysis).
"""


import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from django.utils import timezone

from sklearn.metrics import silhouette_score


def segment_customers(customer_queryset, n_clusters=None, return_details=False):
    """
    Compute RFM scores per customer and cluster them with k-means.

    If return_details=True, returns (results, metrics, parameters).
    Otherwise returns results list.
    """
    default_metrics = {"silhouette_score": 0.0, "num_customers": 0, "k": 3}
    default_params = {"algorithm": "K-Means RFM", "n_clusters": 3}

    try:
        if n_clusters is None:
            try:
                from analytics.models import SystemSetting
                n_clusters = SystemSetting.get_settings().customer_segment_clusters
            except Exception:
                n_clusters = 3
        n_clusters = max(2, min(6, int(n_clusters)))
        default_params["n_clusters"] = n_clusters

        if not customer_queryset.exists():
            return ([], default_metrics, default_params) if return_details else []

        data = []
        now = timezone.now()
        for customer in customer_queryset:
            orders = customer.orders.all()
            if not orders.exists():
                continue

            recent_order = orders.order_by("-order_date").first()
            recency = (now - recent_order.order_date).days
            frequency = orders.count()
            monetary = sum(
                item.quantity * item.unit_price
                for order in orders
                for item in order.items.all()
            )
            data.append({
                "customer_id": customer.customer_id,
                "customer_name": customer.name,
                "recency": recency,
                "frequency": frequency,
                "monetary": float(monetary),
            })

        if len(data) < 3:
            return (data, default_metrics, default_params) if return_details else data

        df = pd.DataFrame(data)
        features = df[["recency", "frequency", "monetary"]]
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)

        k = min(n_clusters, len(df))
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        df["cluster"] = kmeans.fit_predict(scaled_features)

        sil_score = 0.0
        if len(df) > k and len(set(df["cluster"])) > 1:
            try:
                sil_score = float(silhouette_score(scaled_features, df["cluster"]))
            except Exception:
                sil_score = 0.0

        cluster_means = df.groupby("cluster")[["recency", "frequency", "monetary"]].mean()
        sorted_clusters = cluster_means.sort_values("monetary", ascending=False).index.tolist()

        labels_palette = {
            2: ["High-Value / Frequent", "Low-Frequency / Developing"],
            3: ["VIP/High-Volume", "Regular", "At-Risk/Dormant"],
            4: ["VIP/High-Volume", "Loyal Regular", "Developing", "At-Risk/Dormant"],
            5: ["Champions", "Loyal Regular", "Potential Growth", "At-Risk", "Dormant"],
            6: ["Champions", "High-Spender", "Loyal Regular", "New/Promising", "At-Risk", "Dormant"],
        }
        labels = labels_palette.get(k, ["VIP/High-Volume", "Regular", "At-Risk/Dormant"])

        cluster_to_label = {}
        for i, cluster in enumerate(sorted_clusters):
            cluster_to_label[cluster] = labels[i] if i < len(labels) else f"Tier {i+1}"

        df["cluster_label"] = df["cluster"].map(cluster_to_label)
        records = df.to_dict("records")

        metrics = {
            "silhouette_score": round(sil_score, 3),
            "num_customers": len(df),
            "k": k,
            "inertia": round(float(kmeans.inertia_), 2),
        }

        if return_details:
            return records, metrics, default_params
        return df.drop(columns=["cluster"]).to_dict("records")
    except Exception:
        if return_details:
            return [], default_metrics, default_params
        return []
