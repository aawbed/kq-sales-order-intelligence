# KQ Sales & Order Intelligence System

[![Django CI](https://github.com/aawbed/kq-sales-order-intelligence/actions/workflows/django.yml/badge.svg)](https://github.com/aawbed/kq-sales-order-intelligence/actions/workflows/django.yml)

A Machine Learning-Driven Sales and Order Intelligence System developed for
Kenya Airways's internal water sales and order management operations, as a
final-year project (BSc Informatics and Computer Science, Strathmore
University).

## Core Features

- **Sales Order Management (Figure 3.7b–3.7d):** Real-time booking, line-item totals, order tracking, and flight-critical priority assignment (`Normal`, `High`, `Urgent`).
- **Warehouse Inventory & Fulfilment (Figure 3.7f–3.7g):** Stock levels, safety stock reorder thresholds, automated low-stock warnings, and priority-ranked fulfilment dispatch queue.
- **Financial Billing & Accounts Receivable (Figure 3.7e, 3.7j):** Automated invoice generation with 16% Kenya VAT, multi-channel payment recording (M-Pesa, Bank Transfer, Cash, Cheque, Internal Journal), and accounts receivable aging analysis.
- **Machine Learning Intelligence Layer (Figure 3.5, 3.7h):**
  - **Demand Forecasting:** SARIMAX time-series model predicting daily water order volume with 85% confidence intervals.
  - **Anomaly Detection:** Isolation Forest ensemble flagging statistical spikes and irregular order patterns with Human-in-the-Loop review.
  - **Customer Segmentation:** K-Means clustering performing RFM (Recency, Frequency, Monetary) behavioral analysis.
  - **Model Feedback & Retraining Loop:** Persisted ML run logs, accuracy metrics (MAE, RMSE, MAPE, Silhouette Score, Anomaly Precision), and on-demand model retraining.
- **Enterprise Security & Audit Trail (Figure 3.7k):** Role-Based Access Control (RBAC) across 4 roles, brute-force defense (5 failed attempts lockout), rolling 30-minute idle session timeout, and immutable security audit logs with CSV export.
- **Reporting & Exports (Figure 3.7i):** Generate reports across 5 operational dimensions with branded Kenya Airways ReportLab PDF and CSV downloads.

## User Roles

| Role | Default Landing Screen | Primary Responsibilities |
|---|---|---|
| **Sales Agent** | `/orders/track/` | Create orders, track fulfilment status, review customer order history |
| **Warehouse Officer** | `/inventory/fulfilment/` | Confirm dispatches with stock deduction, monitor stock levels, adjust inventory |
| **Operations Manager** | `/analytics/dashboard/` | Executive dashboard, demand forecasts, review ML anomalies, generate PDF reports, AR |
| **System Administrator** | `/analytics/settings/` | User administration, calibrate ML hyperparameters, audit trail monitoring |

## Project Structure

```text
kq-sales-order-intelligence/
├── .github/workflows/django.yml   # GitHub Actions CI pipeline (migrations + unit & integration tests)
├── accounts/                      # Custom User & Role models, RBAC login, brute-force lockout, profile
├── analytics/                     # Executive dashboard, AR aging, PDF/CSV reports, SystemSetting
│   └── ml/                        # ML pipeline: SARIMAX forecasting, K-Means RFM, Isolation Forest
├── config/                        # Django project settings, root URL routing, WSGI/ASGI entrypoints
├── core/                          # RBAC decorators, immutable AuditLog, Notification engine, seed commands
├── docs/                          # End-user operational manual & production deployment guide
├── inventory/                     # Product catalogue, Stock levels, low-stock alerts, fulfilment queue
├── orders/                        # Customer registry, Order & OrderItem workflow, VAT Invoices & Payments
├── static/                        # Custom KQ stylesheet (custom.css) and Chart.js dashboard scripts
├── templates/                     # Role-tailored Bootstrap 5 templates & printable statement views
├── .env.example                   # Environment variable template (SQLite dev / MySQL production)
├── manage.py                      # Django CLI management entrypoint
└── requirements.txt               # Pinned Python & ML dependencies
```

## Documentation

- 📘 [User Manual](docs/USER_MANUAL.md) — Comprehensive end-user operational manual covering all 4 roles.
- 🚀 [Technical Deployment Guide](docs/DEPLOYMENT_GUIDE.md) — Step-by-step production setup for PythonAnywhere, Cloud MySQL, and Linux VPS.

## Getting Started

1. **Clone and set up a virtual environment:**

   ```bash
   git clone https://github.com/aawbed/kq-sales-order-intelligence.git
   cd kq-sales-order-intelligence
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env for production MySQL credentials, or leave DB_ENGINE unset for local SQLite
   ```

3. **Apply database migrations:**

   ```bash
   python manage.py migrate
   ```

4. **Seed realistic demo data & initialize ML models:**

   ```bash
   python manage.py seed_demo_data
   python manage.py retrain_models
   ```

5. **Run the automated test suite:**

   ```bash
   python manage.py test
   ```

6. **Start the development server:**

   ```bash
   python manage.py runserver
   ```

   Visit `http://127.0.0.1:8000/accounts/login/` to sign in.

## Versioning & Releases

- **`v1.0.0` — Initial End-to-End Prototype:** Core 4-role RBAC, Order-to-Cash workflow, and baseline ML modules.
- **`v1.1.0` — Presentation & Demo Mode Release:** Branded KQ UI overhaul, presentation role switcher, PDF/CSV exports, and 27 automated tests.
- **`v1.2.0` — Security Hardening, Workflow Validation & Seasonal ML Release:** Restricted demo persona switching, strict state-machine and stock sufficiency enforcement, weekly SARIMAX seasonality (`s=7`), and composite RFM clustering.

## Licence & Access Conditions

This repository is developed and submitted as an academic final-year project for the **Bachelor of Science in Informatics and Computer Science** at **Strathmore University**. All source code is publicly accessible for academic examination and supervisor evaluation under educational use terms.

