from flask import Blueprint
import os
from jwt import PyJWKClient
from core.extensions import oauth


# Initialize admin blueprint
admin_bp = Blueprint("admin", __name__)
adminauth = Blueprint("adminauth", __name__, url_prefix="/adminauth")

# Import routes AFTER initializing blueprint
from naledi.adminchain import adminroutes


def register_azure_for_official():

    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")

    #AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    if not AZURE_TENANT_ID:
        raise ValueError("Azure Tenant ID is missing.")

    jwks_client = PyJWKClient(os.getenv("AZURE_JWKS_URL"))

    azure = oauth.register(
        name='azure',
        client_id=os.getenv('AZURE_CLIENT_ID'),
        client_secret=os.getenv('AZURE_CLIENT_SECRET'),
        authorize_url=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/authorize',
        access_token_url=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token',
        api_base_url='https://graph.microsoft.com/',
        client_kwargs={'scope': 'openid email profile'},
        jwks_uri=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys',
        redirect_uri=os.getenv("AZURE_REDIRECT_URI")
    )

    return azure, jwks_client
