import os
from flask import Flask, Blueprint,g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from core.naledimodels import User, UserProfile
from core.extensions import db, oauth, migrate, mail, generate_serializer
from flask_mailman import Mail
from itsdangerous import URLSafeTimedSerializer
#from ldap3 import Server, Connection, ALL  # For AD authentication
from flask.helpers import get_root_path
import dash
import dash_bootstrap_components as dbc
from core.naledimodels import StoreDetails
from flask import current_app
import re
import jwt, requests
from jwt import PyJWKClient,InvalidTokenError
from msal import ConfidentialClientApplication
from flask_session import Session
import google.auth
from google.auth import  default, identity_pool
from google.cloud import storage
from google.oauth2.credentials import Credentials
from flask_wtf import CSRFProtect



load_dotenv()





dotenv_path = os.path.join(os.path.dirname(__file__), "env", ".env.preprod.store")

#if not os.path.exists(dotenv_path):
#   print("❌ error: .env.preprod.store file not found")
#    exit(1)

load_dotenv(dotenv_path=dotenv_path, verbose=True)

csrf = CSRFProtect()

# Define the naledi blueprint at the module level
naledi_bp = Blueprint('naledi', __name__)


# ✅ Initialize two login managers
user_login_manager = LoginManager()
#user_login_manager.session_protection = "strong"
#user_login_manager.login_view = 'naledi.naledi_login'  # Store users login page

admin_manager = LoginManager()
#admin_manager.session_protection = "strong"
#admin_manager.login_view = 'naledi.naledi_admin_login'  # Admin login page

official_login_manager = LoginManager()





print("azure reditect uri",os.getenv('AZURE_REDIRECT_URI'))

# Initialize OAuth and register Azure AD as an OAuth client
# Retrieve tenant ID
#AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
#if not AZURE_TENANT_ID:
#    raise ValueError("Azure Tenant ID is missing. Set the AZURE_TENANT_ID environment variable.")


# Retrieve the GCP audiwnce
GCP_AUDIENCE =os.getenv("GCP_AUDIENCE").strip()

print(f"✅ GCP Audience Loaded inside init  before get_credentials : {GCP_AUDIENCE}")

# Retrieve configuration values
def get_credentials():
    """Fetch Workforce Identity Federation credentials."""
    WORKFORCE_POOL_ID = os.getenv("WORKFORCE_POOL_ID")
    PROVIDER_ID = os.getenv("WORKFORCE_PROVIDER_ID")
    SERVICE_ACCOUNT_EMAIL = os.getenv("SERVICE_ACCOUNT_EMAIL")
    #GCP_AUDIENCE = f"//iam.googleapis.com/locations/global/workforcePools/{WORKFORCE_POOL_ID}/providers/{PROVIDER_ID}"

    print(f"✅ GCP Audience Loaded inside init app callback: {GCP_AUDIENCE}")


    credentials = identity_pool.Credentials.from_info({
        "type": "external_account",
        "audience": GCP_AUDIENCE,
        "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
        "token_url": "https://sts.googleapis.com/v1/token",
        "credential_source": {
            "file": os.getenv("OIDC_TOKEN_PATH")  # Path to your OIDC token
        },
        "service_account_impersonation_url": f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{SERVICE_ACCOUNT_EMAIL}:generateAccessToken",
    })
    return credentials


# temporary function to try and get an azure token for exhange with a googl access token.
# this function needs to be called in the azure callback 
def exchange_id_token_for_access_token(id_token):
    sts_url = "https://sts.googleapis.com/v1/token"
    audience = GCP_AUDIENCE  # Already loaded

    print(f"✅ GCP Audience Loaded inside exchange ID token function: {audience}")

    if not audience:
        raise Exception("❌ GCP_AUDIENCE not set in environment.")

    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "audience": audience,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "subject_token": id_token
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(sts_url, data=data, headers=headers)

    if response.status_code == 200:
        access_token = response.json().get("access_token")
        print("✅ STS token exchange success.")
        return access_token
    else:
        print(f"❌ Token exchange failed: {response.json()}")
        raise Exception("STS Token Exchange Failed")


def get_storage_client(access_token):
    creds = Credentials(token=access_token)
    return storage.Client(credentials=creds)


# include the bucket-name for official users
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
if not GCS_BUCKET_NAME:
    raise ValueError("GCS Bucket Name is missing. Set the GCS_BUCKET_NAME environment variable.")


def create_app(app_type="store"):
    """Application factory pattern"""
   
    #app = Flask(__name__) maybe try the below line

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    TEMPLATE_DIR = os.path.join(BASE_DIR, "../naledi/templates")
    STATIC_DIR = os.path.join(BASE_DIR, "../naledi/static")

    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)

    #app = Flask(__name__, template_folder="/naledi/templates")


    app.config.from_object("core.config.DevelopmentConfig")

    # ✅ Initialize extensions
    db.init_app(app)
    oauth.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    app.serializer = generate_serializer(app)
    csrf.init_app(app) # CSRF Protection
    
   

    if app_type is None:
        app_type = os.getenv("FLASK_APP_TYPE", "store")  # Default to store

    print(f"✅ Flask App Type: {app_type}")  # Debugging

    # ✅ Setup login manager based on app type
    if app_type == "store":
        user_login_manager.init_app(app)  # Normal users only
    elif app_type == "official":
        official_login_manager.init_app(app)  # Official users
    elif app_type == "admin":
        print("Admin login manager initialized")
        admin_manager.init_app(app)  # Admin users

    # ✅ Register Google OAuth (Always Needed for Store Users)
    if app_type == "store":
        google = oauth.register(
            name="google",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            access_token_url="https://oauth2.googleapis.com/token",
            authorize_url="https://accounts.google.com/o/oauth2/auth",
            api_base_url="https://www.googleapis.com/oauth2/v1/",
            userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
            client_kwargs={"scope": "openid email profile"},
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            redirect_uri=os.getenv("GOOGLE_REDIRECT_URI_PROD")
        )

    # ✅ Register Store-Specific Blueprints
    if app_type == "store":
        from naledi.spazachain.spachainauth import spachainauth
        from naledi.spazachain.spachainview import spachainview
        app.register_blueprint(spachainauth, url_prefix='/spazachain')
        app.register_blueprint(spachainview, url_prefix='/spazachain/view')

    # ✅ Register Official-Specific Blueprints (Only for `official`)
    if app_type in ("admin","official"):

        from core.oauth import setup_azure_oauth
        azure, jwks_client = setup_azure_oauth(oauth)

        """if app_type == "official":
             AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
        if not AZURE_TENANT_ID:
            raise ValueError("Azure Tenant ID is missing. Set the AZURE_TENANT_ID environment variable.") """

    
        app.config['AD_SERVER'] = os.getenv("AD_SERVER")  # e.g., ldap://your-ad-server
        app.config['AD_DOMAIN'] = os.getenv("AD_DOMAIN")  # e.g., municipality.gov
        from naledi.mncchain.mncauth import mncauth
        from naledi.mncchain.mncview import mncview
        app.register_blueprint(mncauth, url_prefix='/mncauth')
        app.register_blueprint(mncview, url_prefix='/mncview')

    # ✅ Register Admin-Specific Blueprints **Outside the If Statement**
    from naledi.adminchain.adminroutes import admin_bp 
    from naledi.adminchain.adminauth import adminauth

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(adminauth, url_prefix="/admin")


    #from mncchain.mncauth import mncauth
    #from mncchain.mncview import mncview
    #app.register_blueprint(mncauth, url_prefix='/mncauth')
    #app.register_blueprint(mncview, url_prefix='/mncview')
    

    # ✅ Register Naledi Blueprints (Always Needed)
    from core.routes import naledi_bp
    app.register_blueprint(naledi_bp, url_prefix='/')

    # ✅ Configure Upload Folder and Sessions
    app.config['UPLOAD_FOLDER'] = 'uploads/'
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True

    Session(app)
    return app