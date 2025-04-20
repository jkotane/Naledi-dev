# naledi/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager,login_user
from authlib.integrations.flask_client import OAuth
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer
from flask_migrate import Migrate
from flask_mailman import Mail
#from ldap3 import Server, Connection, ALL
from flask import current_app
from authlib.integrations.flask_client import OAuth

# Initialize the extensions globally
db = SQLAlchemy()

""""
login_manager = LoginManager()
login_manager.login_view = "naledi.naledi_login"
admin_manager = LoginManager()
admin_manager.login_view = "naledi.naledi_admin_login"
"""


oauth = OAuth()
migrate = Migrate()  # Initialize Migrate
mail = Mail()  # Initialize Mail
#s = None

def generate_serializer(app):
    return URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Define `s` globally but do not initialize it yet


# Define the to authenticate a user against Active Directory using an LDAP function 
# The user send the official credentials to the LDAP server throught the flask app
# The flask app senda bidn request to the LDAPm server
# The function returns True if the user is authenticated and False otherwise

# def authenticate_ad_user(username, password):
#     """Authenticate a user against Active Directory."""
#     try:
#         server = Server(current_app.config['AD_SERVER'], get_info=ALL)
#         conn = Connection(server, user=f'{username}@{current_app.config["AD_DOMAIN"]}', password=password)
#         if conn.bind():
#             login_user(username)
#             return True
#             #flash("Invalid username or password. Please try again.", "danger")
#         return False
#     except Exception as e:
#         print(f"AD Authentication Error: {e}")
#         return False