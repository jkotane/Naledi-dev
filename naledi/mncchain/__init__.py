# from flask import Blueprint

# # Define Blueprints for MNCChain
# mncauth = Blueprint("mncauth", __name__, url_prefix='/mncchain/auth')
# mncview= Blueprint("mncview", __name__, url_prefix='mncview/view')

# Import routes after defining Blueprint to avoid circular imports

from flask import Flask
from core import db, oauth, migrate, mail, csrf, generate_serializer, official_login_manager
from flask_session import Session
from flask_login import LoginManager
from core import get_credentials, exchange_id_token_for_access_token
from core.oauth_setup import setup_azure_oauth
from naledi.mncchain.mncauth import mncauth
from naledi.mncchain.mncview import mncview
from core.official_routes import official_bp
import os




def create_app(app_type=None):
    """Application factory pattern"""
    if app_type is None:
        app_type = os.getenv("FLASK_APP_TYPE")

    if not app_type:
        raise ValueError("FLASK_APP_TYPE is missing. Specify it as an argument or environment variable.")

    print(f"✅ Flask App Type: {app_type}")
   
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
        app_type = os.getenv("FLASK_APP_TYPE", "official")  # Default to store

        print(f"✅ Flask App Type: {app_type}")  # Debugging

        # ✅ Setup login manager based on app type
   
  
    if app_type == "official":

        official_login_manager.init_app(app)  # Official users

        #from core.oauth_setup import setup_azure_oauth
        azure, jwks_client = setup_azure_oauth(oauth)

        """if app_type == "official":
            AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
        if not AZURE_TENANT_ID:
            raise ValueError("Azure Tenant ID is missing. Set the AZURE_TENANT_ID environment variable.") """

    
        app.config['AD_SERVER'] = os.getenv("AD_SERVER")  # e.g., ldap://your-ad-server
        app.config['AD_DOMAIN'] = os.getenv("AD_DOMAIN")  # e.g., municipality.gov
        from naledi.mncchain.mncauth import mncauth
        from naledi.mncchain.mncview import mncview
        from core.routes import official_bp  # ✅ the new blueprint
        from core.official_routes import official_routes
        app.register_blueprint(official_routes)

        app.register_blueprint(mncauth, url_prefix='/mncauth')
        app.register_blueprint(mncview, url_prefix='/mncview')
        app.register_blueprint(official_bp, url_prefix='/')  # ✅ overrides "/"



    # ✅ Configure Upload Folder and Sessions
    app.config['UPLOAD_FOLDER'] = 'uploads/'
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True

    Session(app)
    return app



