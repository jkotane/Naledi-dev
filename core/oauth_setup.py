import os
import jwt 
from jwt import PyJWKClient, InvalidTokenError


jwks_client = PyJWKClient(os.getenv('AZURE_JWKS_URL'))


def setup_azure_oauth(oauth):
    AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
    if not AZURE_TENANT_ID:
        raise ValueError("Missing AZURE_TENANT_ID")

    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    redirect_uri = os.getenv("AZURE_REDIRECT_URI")
    jwks_url = os.getenv("AZURE_JWKS_URL", "").replace("{AZURE_TENANT_ID}", AZURE_TENANT_ID)

    #jwks_client = PyJWKClient(jwks_url)

    azure = oauth.register(
        name='azure',
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/authorize',
        access_token_url=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token',
        api_base_url='https://graph.microsoft.com/',
        client_kwargs={'scope': 'openid email profile'},
        jwks_uri=jwks_url,
        redirect_uri=redirect_uri
    )

    return azure, jwks_client

# verify the azure token 
def verify_azure_token(id_token):
    """Verify the Azure AD ID token."""
    try:
        # Fetch the signing key for the token

        AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        # Decode and verify the token
        decoded_token = jwt.decode(
            id_token,
            key=signing_key.key,
            algorithms=["RS256"],  # Azure AD uses RS256 for signing
            audience=os.getenv('AZURE_CLIENT_ID'),  # Validate the audience
            AZURE_ISSUER = os.getenv("AZURE_ISSUER", "").replace("{AZURE_TENANT_ID}", AZURE_TENANT_ID),
            options={"verify_exp": True},  # Validate token expiration
        )

        print("Decoded Azure ID Token:", decoded_token)
        return decoded_token

    except InvalidTokenError as e:
        print(f"Invalid token received from Azure: {e}")
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None
