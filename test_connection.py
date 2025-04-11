from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
from sqlalchemy import text

#load_dotenv("env/.env.preprod.store")

dotenv_path = os.path.join(os.path.dirname(__file__), "env", ".env.preprod.store")
load_dotenv(dotenv_path=dotenv_path, verbose=True)

print("dotenv_path", dotenv_path)
print(" The Cloud database  URI :", os.getenv("SQLALCHEMY_DATABASE_URI"))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
db = SQLAlchemy(app)

try:
    with app.app_context():
        result = db.session.execute(text("SELECT NOW();"))
        print("✅ Connected to Cloud SQL! Current time:", result.scalar())
except Exception as e:
    print("❌ Failed to connect:", e)
