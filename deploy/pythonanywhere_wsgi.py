# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# PythonAnywhere WSGI Configuration for KQ Sales & Order Intelligence
# Copy this content into your PythonAnywhere WSGI configuration file:
# /var/www/<your-username>_pythonanywhere_com_wsgi.py
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

import os
import sys

# 1. Add your project directory to the sys.path
path = os.path.expanduser("~/kq-sales-order-intelligence")
if path not in sys.path:
    sys.path.insert(0, path)

# 2. Load environment variables from .env
from dotenv import load_dotenv
project_env = os.path.join(path, ".env")
if os.path.exists(project_env):
    load_dotenv(project_env)

# 3. Set the Django settings module
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

# 4. Import and serve the Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
