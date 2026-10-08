# Kenya Airways Sales & Order Intelligence System — User Manual

**Project Title:** Machine Learning-Driven Sales and Order Intelligence System for Kenya Airways Commercial Water Operations  
**Institution:** Strathmore University — School of Computing and Informatics  
**Document Version:** 1.0 (Production Release)  

---

## 1. System Overview & Architecture

The **Kenya Airways (KQ) Sales & Order Intelligence System** is an enterprise web platform designed to streamline sales order management, warehouse inventory tracking, billing and accounts receivable, and predictive decision-making for Kenya Airways' commercial water unit.

### Key Capabilities
- **Order-to-Cash Workflow:** End-to-end sales booking, inventory allocation, dispatch fulfilment, and invoice generation.
- **Machine Learning Intelligence Layer:**
  - **SARIMAX Time-Series Demand Forecasting:** Predicts daily water case demand with confidence intervals.
  - **Isolation Forest Anomaly Detection:** Flags unexpected demand spikes, dormant-account reactivation, and unusual order volumes.
  - **K-Means RFM Customer Segmentation:** Categorizes corporate customers into behavioral tiers (VIP/High-Volume, Loyal Regular, At-Risk).
- **Security & Regulatory Compliance:**
  - Role-Based Access Control (RBAC) across 4 operational personas.
  - Brute-force login defense (5-attempt lockout).
  - 30-minute rolling idle session timeout.
  - Immutable Security Audit Trail logging all critical transactions.

---

## 2. Getting Started & User Authentication

### 2.1 Logging In
1. Navigate to the system login URL (e.g., `/accounts/login/`).
2. Enter your assigned corporate username and password.
3. Click **Sign In**.
4. The system automatically routes you to your role-specific home screen:
   - **Sales Agent:** Order Creation Screen (`/orders/create/`)
   - **Warehouse Officer:** Stock Levels & Inventory (`/inventory/stock/`)
   - **Operations Manager:** Sales & ML Intelligence Dashboard (`/analytics/dashboard/`)
   - **System Administrator:** System Settings & Configuration (`/analytics/settings/`)

### 2.2 Security Lockout & Idle Sessions
- **Brute-Force Protection:** Entering an invalid password 5 consecutive times temporarily locks the account for 15 minutes. An audit log is recorded, and a countdown timer will display on screen.
- **Session Timeout:** Inactive user sessions automatically expire after 30 minutes of idle time to prevent unauthorized physical terminal access.

---

## 3. Role 1: Sales Agent User Guide

### 3.1 Creating a New Sales Order
1. From the sidebar navigation, select **Create Order**.
2. Select the customer placing the order from the **Customer Account** dropdown.
3. Choose the **Order Priority**:
   - `Normal`: Standard scheduled replenishment.
   - `High`: Time-sensitive turnaround.
   - `Urgent`: Critical aircraft turnarounds and flight departures (elevated to top of warehouse dispatch queue).
4. In the order items table:
   - Select the water product (e.g., *500ml Bottle Case*, *1L Bottle Case*, *20L Dispenser Bottle*).
   - Enter the requested **Quantity**. The unit price and line subtotal calculate automatically.
   - Click **Add Line Item** to include additional packaging sizes.
5. Click **Submit Order**.
6. The order is assigned a unique identifier (e.g., `KQ-1042`) with status `Pending`.

### 3.2 Tracking Orders & Invoices
1. Select **Track Orders** from the sidebar.
2. Review real-time fulfilment statuses:
   - `Pending`: Awaiting sales review and confirmation.
   - `Confirmed`: Approved and dispatched to the warehouse queue.
   - `Fulfilled`: Warehouse has picked, loaded, and deducted stock.
   - `Invoiced`: Billing generated and ready for payment.
3. Use the search bar to locate orders by Order ID or Customer Name.
4. Click **View Details** to inspect line items, priority badges, and download PDF invoices.

### 3.3 Customer Records & Purchase History
1. Navigate to **Customer Records**.
2. View registered corporate accounts, account types (*KQ Internal Department*, *Corporate Client*, *Government Entity*, *Distributor*), and contact records.
3. Click **Order History** on any client to view their historical lifetime purchases and average booking frequency.

---

## 4. Role 2: Warehouse Officer User Guide

### 4.1 Real-Time Stock Monitoring
1. Select **Stock Levels** from the sidebar.
2. View available quantity on hand, unit prices, and configured reorder thresholds.
3. Products below safety thresholds are highlighted with **Low Stock** warning badges.

### 4.2 Stock Adjustments
1. Click **Adjust Stock** on the target product row.
2. Enter the quantity adjustment (+/- offset) and select the operational reason:
   - *Production Batch Receipt*
   - *Inventory Audit Correction*
   - *Breakage / Damage Write-off*
3. Click **Update Level**. The inventory level recalculates and the action is saved to the audit log.

### 4.3 Confirming Fulfilment & Stock Deduction
1. Select **Confirm Fulfilment** from the sidebar.
2. View pending orders queued for dispatch.
   > **Note:** Orders flagged as `Urgent` automatically appear at the top of the queue with danger badges.
3. Verify physical inventory and click **Confirm Fulfilment**.
4. The system automatically:
   - Deducts the order quantity from warehouse stock.
   - Transitions order status to `Fulfilled`.
   - Records an immutable audit log entry.
   - Dispatches automated low-stock warnings if remaining inventory crosses the reorder threshold.

---

## 5. Role 3: Operations Manager User Guide

### 5.1 Sales & ML Intelligence Dashboard
1. Select **Dashboard** from the sidebar navigation.
2. **Executive KPI Cards:**
   - 30-Day Total Sales Revenue (KSh)
   - Weekly Order Volume
   - Active Customers
   - Active Low-Stock Alerts
3. **SARIMAX Demand Forecast Chart:**
   - Interactive line graph displaying predicted unit demand for the upcoming horizon (default 14–30 days).
   - Dynamic 85% statistical confidence bounds.
4. **ML Anomaly Detector (Human-in-the-Loop):**
   - **Open Alerts Tab:** Displays unusual order patterns flagged by Isolation Forest.
   - Click **Review** on any alert to inspect volume spikes and customer history.
   - Choose **Confirmed Anomaly** or **False Positive (Dismiss)**, provide review notes, and submit.
   - Reviewed alerts automatically move to the **Reviewed** tab and recalibrate model precision metrics.
5. **K-Means RFM Customer Segmentation Table:**
   - Evaluates client Recency (days), Frequency (order count), and Monetary value (spend).
   - Classifies accounts into tiers: *VIP/High-Volume*, *Loyal Regular*, and *At-Risk/Dormant*.

### 5.2 Generating Reports (PDF & CSV Export)
1. Select **Generate Reports** from the sidebar.
2. Choose a report type:
   - *Sales Trend Analysis*
   - *Demand Forecasting Projections*
   - *Warehouse Inventory Valuation*
   - *Customer Segmentation Directory*
   - *System Audit Trail*
3. Select date range filters and click **Generate Report**.
4. Preview the interactive report table on screen.
5. Click **Export to CSV** for Excel spreadsheets, or **Download Branded PDF** for executive Kenya Airways presentation reports with tables and totals.

### 5.3 Accounts Receivable & Payment Recording
1. Select **Accounts Receivable** from the sidebar.
2. Monitor collection metrics: Total Invoiced, Total Collected, Total Outstanding, and Collection Rate.
3. Review the **Aging Buckets Summary**:
   - `Current` (Within terms)
   - `1 - 30 Days`
   - `31 - 60 Days`
   - `61 - 90 Days`
   - `Over 90 Days` (Overdue)
4. To record a payment against an invoice:
   - Click **Record Payment**.
   - Enter payment amount and choose the payment method:
     - *M-Pesa (Paybill)*
     - *Bank Transfer (EFT)*
     - *Cash*
     - *Cheque*
     - *Internal Journal Transfer*
   - Enter reference number (e.g., M-Pesa transaction code or cheque number).
   - Click **Save Payment**. Invoice balance updates instantly.

### 5.4 ML Model Performance & Retraining
1. Select **Model Performance** from the sidebar.
2. Inspect validation metrics:
   - **SARIMAX:** Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Mean Absolute Percentage Error (MAPE).
   - **K-Means:** Silhouette Coefficient (-1 to +1 cluster separation), Inertia.
   - **Isolation Forest:** Contamination rate, Flagged anomalies count, Review precision percentage.
3. Click **Retrain Models** to trigger an on-demand re-fitting of models against the latest transactions.

---

## 6. Role 4: System Administrator User Guide

### 6.1 User Management & Role Assignment
1. Select **Manage Users** from the sidebar.
2. View active accounts, assigned roles, and login statuses.
3. Click **Create New User**:
   - Fill in username, email, full name, and initial password.
   - Select role: *Sales Agent*, *Warehouse Officer*, *Operations Manager*, or *System Administrator*.
4. Edit existing accounts or toggle active status to instantly revoke access.

### 6.2 System Configuration Parameters
1. Select **System Settings** from the sidebar.
2. **Forecasting Parameters:**
   - Adjust Confidence Threshold (0.50 – 0.99)
   - Adjust Forecast Horizon (7 – 90 days)
3. **Anomaly Parameters:**
   - Calibrate Isolation Forest Contamination Rate (0.01 – 0.25)
4. **Alert & Notification Toggles:**
   - Enable/disable low stock alerts to warehouse officers.
   - Enable/disable anomaly alert emails to operations managers.
5. Click **Save Configuration**. Changes take effect immediately.

### 6.3 Security Audit Trail
1. Select **Security Audit Trail** from the sidebar.
2. Review immutable log records capturing:
   - Timestamp, Actor (User), Action Type, IP Address, Target Entity, and Description.
3. Filter by Action Type (*Login*, *Failed Login*, *Account Lockout*, *Order Created*, *Stock Adjusted*, *Payment Recorded*).
4. Click **Export Audit Log (CSV)** for external compliance and forensic audits.
