from flask import Blueprint

# Define Blueprints for MNCChain
mncauth = Blueprint("mncauth", __name__, url_prefix='/mncchain/auth')
mncview= Blueprint("mncview", __name__, url_prefix='mncview/view')

# Import routes after defining Blueprint to avoid circular imports






