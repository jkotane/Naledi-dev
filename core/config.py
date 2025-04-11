import os
from flask_session import Session
from dotenv import load_dotenv
from google.cloud import secretmanager
from itsdangerous import URLSafeTimedSerializer

# Load environment variables from .env
load_dotenv()

# Set credentials
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = get_secret("google-credentials")

# Correct path joining
dotenv_path = os.path.join(os.path.dirname(__file__), "env", ".env.preprod.store")

# Get the Flask environment, default to "production" if not set
FLASK_ENV = os.getenv("FLASK_ENV", "production")

# Determine if running locally
IS_LOCAL = FLASK_ENV == "development"

# Set the correct Google Redirect URI
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI_LOCAL") if IS_LOCAL else os.getenv("GOOGLE_REDIRECT_URI_PROD")


SESSION_TYPE = 'filesystem'  # Stores sessions on the server instead of cookies
SESSION_PERMANENT = False
SESSION_USE_SIGNER = True
SESSION_FILE_DIR = "./flask_session"


print(f"Flask Environment: {FLASK_ENV}")
print(f"Using GOOGLE_REDIRECT_URI: {GOOGLE_REDIRECT_URI}")


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    #FLASK_ENV = get_secret("FLASK_ENV")

    # Database: Enforce PostgreSQL, raise error if DATABASE_URL is missing
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("❌ ERROR: DATABASE_URL is not set! Flask cannot start.")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    #GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', "http://127.0.0.1:5000/auth/google/callback")

    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads/')
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')
   
    

class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

