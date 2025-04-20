from flask import Flask
from core.extensions import db, oauth, migrate, mail, generate_serializer, csrf
from naledi.spazachain.spachainauth import spachainauth
from naledi.spazachain.spachainview import spachainview
from core.routes import naledi_bp

def create_app_store():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object("core.config.DevelopmentConfig")

    db.init_app(app)
    oauth.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    app.serializer = generate_serializer(app)
    csrf.init_app(app)

    # Google OAuth registration
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        api_base_url="https://www.googleapis.com/oauth2/v1/",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        client_kwargs={"scope": "openid email profile"},
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        redirect_uri=app.config["GOOGLE_REDIRECT_URI_PROD"]
    )

    # Register blueprints
    app.register_blueprint(spachainauth, url_prefix='/spazachain')
    app.register_blueprint(spachainview, url_prefix='/spazachain/view')
    app.register_blueprint(naledi_bp, url_prefix='/')

    return app
