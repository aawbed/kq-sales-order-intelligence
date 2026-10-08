"""
Anomaly detection module.

Implements Isolation Forest to flag unusual order patterns (e.g. sudden
demand spikes, dormant-account reactivation) for the Operations
Manager's ML Anomaly Detector panel on the Sales Dashboard.
"""


import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_anomalies(order_queryset, contamination=None):
    """
    Run Isolation Forest over recent order records and return a list
    of flagged anomalies with a short human-readable description.
    """
    try:
        if contamination is None:
            try:
                from analytics.models import SystemSetting
                contamination = SystemSetting.get_settings().anomaly_contamination
            except Exception:
                contamination = 0.05
        contamination = max(0.01, min(0.25, float(contamination)))

        if not order_queryset.exists():
            return []

        data = []
        for order in order_queryset:
            items = order.items.all()
            if not items.exists():
                continue
            quantity = sum(item.quantity for item in items)
            total_value = sum(item.quantity * item.unit_price for item in items)
            freq = order.customer.orders.count()
            
            data.append({
                'order_id': order.order_id,
                'customer_name': order.customer.name,
                'quantity': quantity,
                'total_value': float(total_value),
                'freq': freq
            })

        if len(data) < 5:
            return []

        df = pd.DataFrame(data)
        features = df[['quantity', 'total_value', 'freq']]
        
        iso = IsolationForest(contamination=contamination, random_state=42)
        df['is_anomaly'] = iso.fit_predict(features)
        df['anomaly_score'] = iso.decision_function(features)
        
        anomalies = df[df['is_anomaly'] == -1].copy()
        anomalies['is_anomaly'] = True
        anomalies['anomaly_score'] = anomalies['anomaly_score'].astype(float)
        
        return anomalies[['order_id', 'customer_name', 'anomaly_score', 'is_anomaly']].to_dict('records')
    except Exception as e:
        return []
