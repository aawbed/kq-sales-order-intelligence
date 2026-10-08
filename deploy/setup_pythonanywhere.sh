#!/usr/bin/env bash
# ==============================================================================
# KQ Sales Order Intelligence — PythonAnywhere Automated Setup Script
# Run this script in your PythonAnywhere Bash Console:
#   cd ~/kq-sales-order-intelligence
#   bash deploy/setup_pythonanywhere.sh
# ==============================================================================

set -e

echo "=================================================================="
echo "  KQ Sales & Order Intelligence — Deploying to PythonAnywhere"
echo "=================================================================="

# 1. Determine best available Python 3 version
# Prioritize Python 3.10 on PythonAnywhere as it contains pre-installed scientific libraries (numpy, scipy, pandas, scikit-learn)
if command -v python3.10 &>/dev/null; then
    PY_BIN="python3.10"
elif command -v python3.11 &>/dev/null; then
    PY_BIN="python3.11"
elif command -v python3.12 &>/dev/null; then
    PY_BIN="python3.12"
else
    PY_BIN="python3"
fi

echo "[1/7] Using Python binary: $PY_BIN"

# 2. Set up virtual environment
VENV_DIR="$HOME/.virtualenvs/kq-venv"
if [ -d "$VENV_DIR" ]; then
    if ! grep -q "include-system-site-packages = true" "$VENV_DIR/pyvenv.cfg" 2>/dev/null; then
        echo "[2/7] Re-creating virtual environment with system packages to fit disk quota..."
        rm -rf "$VENV_DIR"
        $PY_BIN -m venv --system-site-packages "$VENV_DIR"
    else
        echo "[2/7] Virtual environment already exists with system packages at $VENV_DIR."
    fi
else
    echo "[2/7] Creating virtual environment with system packages at $VENV_DIR..."
    $PY_BIN -m venv --system-site-packages "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# 3. Install project dependencies
echo "[3/7] Installing project dependencies (reusing system packages to save disk)..."
pip install --no-cache-dir -r requirements.txt

# 4. Configure .env if not present
if [ ! -f ".env" ]; then
    echo "[4/7] Generating production .env file..."
    SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(50))')
    cp .env.example .env
    sed -i "s/change-this-to-a-random-secret-key/$SECRET_KEY/" .env
    sed -i "s/DJANGO_DEBUG=True/DJANGO_DEBUG=False/" .env
    sed -i "s/DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1/DJANGO_ALLOWED_HOSTS=.pythonanywhere.com,localhost,127.0.0.1/" .env
    echo "      Generated .env with secure random secret key."
else
    echo "[4/7] .env configuration already present."
fi

# 5. Database migrations
echo "[5/7] Applying database migrations..."
python manage.py migrate

# 6. Static files collection
echo "[6/7] Collecting static assets..."
python manage.py collectstatic --noinput

# 7. Seed demo database and train ML intelligence models
echo "[7/7] Seeding demo orders & training initial ML models..."
python manage.py seed_demo_data
python manage.py retrain_models

echo ""
echo "=================================================================="
echo "  DEPLOYMENT INITIALIZATION COMPLETE!"
echo "=================================================================="
echo ""
echo "Next step in your PythonAnywhere Web tab:"
echo "1. Go to the 'Web' tab on PythonAnywhere."
echo "2. Set 'Source code': $HOME/kq-sales-order-intelligence"
echo "3. Set 'Virtualenv': $VENV_DIR"
echo "4. Under 'Code', click the WSGI configuration file link and replace"
echo "   its contents with deploy/pythonanywhere_wsgi.py."
echo "5. Under 'Static files', add a mapping:"
echo "   - URL: /static/"
echo "   - Directory: $HOME/kq-sales-order-intelligence/staticfiles"
echo "6. Click the green 'Reload <your-username>.pythonanywhere.com' button."
echo ""
