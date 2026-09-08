"""
Customer segmentation module.

Implements RFM (Recency, Frequency, Monetary)-based k-means clustering
to segment customers by purchasing behaviour, as reviewed in Chapter 2
(Customer Sales Trend Analysis).
"""


def segment_customers(customer_queryset):
    """
    Compute RFM scores per customer and cluster them with k-means.

    Placeholder implementation — to be built out with scikit-learn's
    KMeans once RFM feature extraction from Order/Invoice data is defined.
    """
    raise NotImplementedError("RFM k-means segmentation not yet implemented")
