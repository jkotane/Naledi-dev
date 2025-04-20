# core/__init__.py

from flask_sqlalchemy import SQLAlchemy
from flask_mailman import Mail
from flask_migrate import Migrate
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from flask_wtf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer

# Extensions
db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
oauth = OAuth()
csrf = CSRFProtect()

# Multiple login managers
user_login_manager = LoginManager()
official_login_manager = LoginManager()
admin_manager = LoginManager()

# Serializer utility
def generate_serializer(app):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

__all__ = [
    "db", "mail", "migrate", "oauth", "csrf",
    "user_login_manager", "official_login_manager", "admin_manager",
    "generate_serializer"
]
