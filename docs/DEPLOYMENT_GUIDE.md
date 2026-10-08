# Kenya Airways Sales & Order Intelligence System — Technical Deployment Guide

**Target Environments:** PythonAnywhere (Primary Cloud Host) / Railway / Docker / Linux VPS  
**Database:** Cloud MySQL 8.0 (Production) / SQLite 3 (Development)  
**Framework:** Django 4.2 LTS / Python 3.12  
**Document Version:** 1.0  

---

## 1. Prerequisites & System Requirements

### Minimum Server Specifications
- **Python:** Python 3.10, 3.11, or 3.12 (Python 3.12 recommended)
- **Database:** MySQL 8.0 or MariaDB 10.5+ (or SQLite 3 for local development)
- **RAM:** Minimum 512 MB (1 GB recommended for scikit-learn & statsmodels model execution)
- **Disk:** 500 MB free storage

### Required System Packages (Debian/Ubuntu/Linux)
```bash
sudo apt-get update
sudo apt-get install -y default-libmysqlclient-dev pkg-config build-essential python3-dev
```

---

## 2. Option A: PythonAnywhere Deployment (Step-by-Step)

PythonAnywhere is the recommended hosting environment specified in the project proposal.

### Step 2.1: Clone Repository into PythonAnywhere
Open a **Bash Console** from your PythonAnywhere Dashboard:
```bash
git clone https://github.com/aawbed/kq-sales-order-intelligence.git
cd kq-sales-order-intelligence
```

### Step 2.2: Automated Setup Script
Run the automated deployment script:
```bash
bash deploy/setup_pythonanywhere.sh
```
This script automatically:
1. Creates virtual environment at `~/.virtualenvs/kq-venv`.
2. Installs all dependencies from `requirements.txt`.
3. Creates a secure `.env` file with random secret key and production configurations.
4. Applies all database migrations.
5. Collects static assets to `staticfiles/`.
6. Seeds the database with realistic demo accounts and transactions.
7. Trains initial SARIMAX, K-Means, and Isolation Forest models.

---

### Step 2.3: Configure the Web App in PythonAnywhere
1. In the PythonAnywhere top menu, click **Web**.
2. Click **Add a new web app**.
3. Choose **Manual configuration** (NOT the Django wizard, since the project is already structured).
4. Select **Python 3.12** (or matching your installed version).
5. In the Web App configuration screen:
   - **Source code:** Set to `/home/<your-username>/kq-sales-order-intelligence`
   - **Working directory:** Set to `/home/<your-username>/kq-sales-order-intelligence`
   - **Virtualenv:** Set to `/home/<your-username>/.virtualenvs/kq-venv`

---

### Step 2.4: Configure WSGI File
1. Under the **Code** section, click on the **WSGI configuration file** link (`/var/www/<username>_pythonanywhere_com_wsgi.py`).
2. Delete the default template content.
3. Replace with the following snippet (also available in `deploy/pythonanywhere_wsgi.py`):

```python
import os
import sys

# 1. Add project directory to sys.path
path = os.path.expanduser("~/kq-sales-order-intelligence")
if path not in sys.path:
    sys.path.insert(0, path)

# 2. Load environment variables from .env
from dotenv import load_dotenv
project_env = os.path.join(path, ".env")
if os.path.exists(project_env):
    load_dotenv(project_env)

# 3. Set Django settings
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

# 4. Serve WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
4. Click **Save** at the top right.

---

### Step 2.5: Configure Static Files Mapping
Under the **Static files** section of the Web tab, configure the mapping:
| URL | Directory Path |
|---|---|
| `/static/` | `/home/<your-username>/kq-sales-order-intelligence/staticfiles` |

---

### Step 2.6: Configure Cloud MySQL Database (Optional / Production)
To connect to PythonAnywhere's managed MySQL database:
1. Go to the **Databases** tab on PythonAnywhere.
2. Initialize your MySQL password.
3. Create a database named `kq_sales_order_intelligence`.
4. Open your `.env` file (`nano ~/kq-sales-order-intelligence/.env`) and update:
   ```env
   DB_ENGINE=mysql
   DB_NAME=<your-username>$kq_sales_order_intelligence
   DB_USER=<your-username>
   DB_PASSWORD=<your-mysql-password>
   DB_HOST=<your-username>.mysql.pythonanywhere-services.com
   DB_PORT=3306
   ```
5. Run migrations in your virtualenv console:
   ```bash
   source ~/.virtualenvs/kq-venv/bin/activate
   python manage.py migrate
   python manage.py seed_demo_data
   python manage.py retrain_models
   ```

---

### Step 2.7: Reload & Verify
1. Return to the **Web** tab.
2. Click the green **Reload <your-username>.pythonanywhere.com** button.
3. Open `https://<your-username>.pythonanywhere.com` in your browser.
4. Log in using default credentials or your created administrator account:
   - **Username:** `admin`
   - **Password:** `Password123!`

---

## 3. Option B: Local or Virtual Private Server (VPS) Deployment

### 3.1 Environment Setup
```bash
# 1. Clone repository
git clone https://github.com/aawbed/kq-sales-order-intelligence.git
cd kq-sales-order-intelligence

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env
```

### 3.2 Initialize Database
```bash
# Run migrations
python manage.py migrate

# Populate sample data (15+ corporate clients, 250+ historical orders, inventory)
python manage.py seed_demo_data

# Train and calibrate initial ML models
python manage.py retrain_models

# Collect static files
python manage.py collectstatic --noinput
```

### 3.3 Run Local Development Server
```bash
python manage.py runserver 8000
```
Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your web browser.

---

## 4. Continuous Integration (CI) Pipeline

The repository includes automated CI via **GitHub Actions** (`.github/workflows/django.yml`):
- Runs automatically on every `push` and `pull_request` targeting `main`.
- Sets up Python 3.12 and installs system C libraries (`default-libmysqlclient-dev`).
- Runs `python manage.py migrate`.
- Executes the full 16-test suite (unit tests and order-to-cash integration test).
- Status badge updates live on `README.md`.
