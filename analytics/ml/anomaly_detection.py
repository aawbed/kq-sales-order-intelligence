"""
Anomaly detection module.

Implements Isolation Forest to flag unusual order patterns (e.g. sudden
demand spikes, dormant-account reactivation) for the Operations
Manager's ML Anomaly Detector panel on the Sales Dashboard.
"""


def detect_anomalies(order_queryset):
    """
    Run Isolation Forest over recent order records and return a list
    of flagged anomalies with a short human-readable description.

    Placeholder implementation — to be built out with scikit-learn's
    IsolationForest once feature engineering on order data is defined.
    """
    raise NotImplementedError("Isolation Forest anomaly detector not yet implemented")
