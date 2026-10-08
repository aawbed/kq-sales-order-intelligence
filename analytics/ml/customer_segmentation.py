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

def segment_customers(customer_queryset, n_clusters=None):
    """
    Compute RFM scores per customer and cluster them with k-means.
    """
    try:
        if n_clusters is None:
            try:
                from analytics.models import SystemSetting
                n_clusters = SystemSetting.get_settings().customer_segment_clusters
            except Exception:
                n_clusters = 3
        n_clusters = max(2, min(6, int(n_clusters)))

        if not customer_queryset.exists():
            return []

        data = []
        now = timezone.now()
        for customer in customer_queryset:
            orders = customer.orders.all()
            if not orders.exists():
                continue
            
            recent_order = orders.order_by('-order_date').first()
            recency = (now - recent_order.order_date).days
            frequency = orders.count()
            monetary = sum(
                item.quantity * item.unit_price 
                for order in orders 
                for item in order.items.all()
            )
            data.append({
                'customer_id': customer.customer_id,
                'customer_name': customer.name,
                'recency': recency,
                'frequency': frequency,
                'monetary': float(monetary)
            })

        if len(data) < 3:
            return data

        df = pd.DataFrame(data)
        features = df[['recency', 'frequency', 'monetary']]
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(features)
        
        k = min(n_clusters, len(df))
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(scaled_features)
        
        cluster_means = df.groupby('cluster')[['recency', 'frequency', 'monetary']].mean()
        sorted_clusters = cluster_means.sort_values('monetary', ascending=False).index.tolist()
        
        labels_palette = {
            2: ['High-Value / Frequent', 'Low-Frequency / Developing'],
            3: ['VIP/High-Volume', 'Regular', 'At-Risk/Dormant'],
            4: ['VIP/High-Volume', 'Loyal Regular', 'Developing', 'At-Risk/Dormant'],
            5: ['Champions', 'Loyal Regular', 'Potential Growth', 'At-Risk', 'Dormant'],
            6: ['Champions', 'High-Spender', 'Loyal Regular', 'New/Promising', 'At-Risk', 'Dormant'],
        }
        labels = labels_palette.get(k, ['VIP/High-Volume', 'Regular', 'At-Risk/Dormant'])

        cluster_to_label = {}
        for i, cluster in enumerate(sorted_clusters):
            cluster_to_label[cluster] = labels[i] if i < len(labels) else f'Tier {i+1}'
            
        df['cluster_label'] = df['cluster'].map(cluster_to_label)
        return df.drop(columns=['cluster']).to_dict('records')
    except Exception as e:
        return []
