# KQ Sales & Order Intelligence System

A Machine Learning-Driven Sales and Order Intelligence System developed for
Kenya Airways's internal water sales and order management operations, as a
final-year project (BSc Informatics and Computer Science, Strathmore
University).

This repository implements the design specified in Chapter Three of the
project proposal: the class diagram, entity relationship diagram, database
schema, system architecture, and wireframes.

## Tech stack

- **Backend:** Python / Django 4.2
- **Frontend:** Bootstrap 5 (server-rendered Django templates)
- **Database:** MySQL (production), SQLite (local development)
- **ML pipeline:** scikit-learn (Isolation Forest, k-means), statsmodels (SARIMAX)

## Project structure

See `docs/proposal/` for the full Chapter Three design artefacts (diagrams,
ERD, schema, wireframes) that this codebase implements.

| App | Responsibility | Corresponding entities |
|---|---|---|
| `accounts` | Authentication, roles, user management | User, Role |
| `orders` | Core sales domain | Customer, Order, OrderItem, Invoice, Payment |
| `inventory` | Warehouse domain | Product, Stock |
| `analytics` | Reporting and ML pipeline | Report |
| `core` | Shared utilities (role-based permissions) | — |

## Getting started

1. **Clone and set up a virtual environment:**

   ```bash
   git clone <repo-url>
   cd kq-sales-order-intelligence
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # edit .env with your local DB credentials, or leave DB_ENGINE unset
   # to use SQLite for local development
   ```

3. **Run migrations and create a superuser:**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Run the development server:**

   ```bash
   python manage.py runserver
   ```

   Visit `http://127.0.0.1:8000/accounts/login/` to sign in.

## Git workflow

- `main` — stable, working code only.
- Feature branches per screen/module (e.g. `feature/create-order-form`).
- Commit early and often; open a PR into `main` when a feature is complete.
- Pull (`git pull origin main`) before starting new work each session to
  avoid divergent history, since this is a solo repository with sequential
  development sessions.

## Status

Project scaffold: models, URLs, views, and template stubs are in place for
all 11 screens identified in the Use Case Diagram (Figure 3.2) and Wireframes
(Figure 3.7a–3.7k). ML pipeline modules (`analytics/ml/`) are stubbed pending
implementation. UI styling is at wireframe fidelity pending the design pass.
