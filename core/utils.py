# naledi/utils.py
import re
from google.cloud import storage
from google.auth.transport.requests import Request
from google.auth import identity_pool
from google.auth import credentials
from datetime import timedelta
#from ldap3 import Server, Connection, ALL
from flask import current_app,g
from dash import dash_table,dcc,html
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
from core.extensions import db  # Importing SQLAlchemy from your Flask app
from core.naledimodels import StoreDetails,MncUser,Document  # Import your existing model
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import google.auth
from google.auth import  default
from google.cloud import storage
from  core import get_credentials, exchange_id_token_for_access_token, get_storage_client
from google.auth import load_credentials_from_file
from google.auth.transport.requests import Request
import json
import requests
from google.cloud import storage
from google.oauth2.credentials import Credentials
import os
from flask import session
import sys
from dotenv import load_dotenv



ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}


# password check helper functions design for the Official IUser 

def set_password(password):
    """Hashes and returns the hashed password."""
    return generate_password_hash(password, method="pbkdf2:sha256")

def check_password(stored_hash, password):
    """Checks if the provided password matches the stored hash."""
    return check_password_hash(stored_hash, password)


def save_password(self, password):
        """Hashes and saves the user's password."""
        self.password_hash = set_password(password)

def verify_password(self, password):
        """Verifies if the provided password matches the stored hash."""
        return check_password(self.password_hash, password)

@staticmethod
def verify_registration_token(token):
        """Verify the token and return the user."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = s.loads(token, salt="registration", max_age=86400)  # 1-day expiry
        except:
            return None
        return MncUser.query.filter_by(mnc_email=email).first()


# Validation helper function for email
def is_valid_email(email):
    """Validate email format."""
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(regex, email)


# Validation helper function for cell number
def is_valid_cellno(cellno):
    """Validate South African cell number format."""
    regex = r'^(0|\+27)[6-8][0-9]{8}$'
    return re.match(regex, cellno)

def generate_registration_token(self):
        """Generate a secure token for user registration."""
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(self.mnc_email, salt="registration")


# ✅ Verify Reset Token
@staticmethod
def verify_reset_token(token, expires_sec=1800):
    """Verify a password reset token and return the user ID if valid."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        user_data = serializer.loads(token, salt='password-reset', max_age=expires_sec)
        return user_data['user_id']
    except Exception:
        return None  # Token is invalid or expired



#def get_storage_client():
#    """Returns a Google Cloud Storage client, initializes if not set."""
#    if 'storage_client' not in g:
#        creds, project = google.auth.default()
#        g.storage_client = storage.Client(credentials=creds)
#    return g.storage_client


# Helper fucntions for store users

# Validation helper function for password
def is_valid_password(password):
    """
    Validate password format.
    Must include:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,}$'
    return re.match(regex, password)

# heloer file to upload documets to Google cloud storage
def upload_to_gcs(file, destination_blob_name):
    """Uploads a file to Google Cloud Storage and returns the file URL."""
    # Initialize a GCS client
    storage_client = storage.Client()

    # The name of your GCS bucket
    bucket_name = 'your-gcs-bucket-name'  # Replace this with your actual bucket name
    bucket = storage_client.bucket(bucket_name)

    # Upload the file to GCS
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(file)

    # Get the public URL of the file
    file_url = blob.public_url
    return file_url

def allowed_file(filename):
    """
    Check if a file is allowed based on its extension.
    
    :param filename: The name of the file
    :param allowed_extensions: A set of allowed file extensions
    :return: True if file extension is allowed, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# utils.py (if you are using this for GCS upload)
from google.cloud import storage

def upload_to_gcs(file, destination_blob_name):
    """Uploads a file to Google Cloud Storage and returns a signed URL for authenticated users."""
    
    # Authenticate with Workload Identity or ADC
    storage_client = storage.Client()

    bucket_name = os.getenv("GCS_BUCKET_NAME", "spaza-docs-bucket")
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload the file
    blob.upload_from_file(file)

    # Generate a signed URL (Valid for 15 minutes)
    #signed_url = blob.generate_signed_url(expiration=timedelta(minutes=15))

    return f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"


def authenticate_ad_user(username, password):
    """Authenticate a user against Active Directory."""
    try:
        server = Server(current_app.config['AD_SERVER'], get_info=ALL)
        conn = Connection(server, user=f'{username}@{current_app.config["AD_DOMAIN"]}', password=password)
        if conn.bind():
            return True
        return False
    except Exception as e:
        print(f"AD Authentication Error: {e}")
        return False
    

# class for AD authentication
class AuthService:
    @staticmethod
    def authenticate_ad_user(username, password):
        """Authenticate a user against Active Directory."""
        try:
            server = Server(current_app.config['AD_SERVER'], get_info=ALL)
            conn = Connection(server, user=f'{username}@{current_app.config["AD_DOMAIN"]}', password=password)
            if conn.bind():
                return True
            return False
        except Exception as e:
            print(f"AD Authentication Error: {e}")
            return False

# Set up logging for debugging
import logging
logging.basicConfig(level=logging.DEBUG)

def fetch_data():
    """Fetch data using SQLAlchemy ORM"""
    stores = StoreDetails.query.with_entities(
        StoreDetails.store_id,
        StoreDetails.store_name,
        StoreDetails.storetype,
        StoreDetails.storeaddress,
        StoreDetails.city,
        StoreDetails.compstatus,
        StoreDetails.ownershipstatus
    ).all()
    

    if not stores:
            logging.warning("No data found in store_details table.")

    # Convert to DataFrame
    df = pd.DataFrame(stores, columns=[
        "id", "store_name", "storetype", "storeaddress", "city", "compstatus", "ownershipstatus"
    ])
    logging.debug(f"Fetched {len(df)} records.")
    print(df)   
    return df

def generate_dashboard_layout():
    df = fetch_data()
    print("Data in generate_dashboard_layout():", df) 
    logging.debug(f"Data in generate_dashboard_layout(): {df}")
    
    # Metrics
    total_stores = len(df)
    compliant_stores = df[df["compstatus"] == "Compliant"].shape[0]
    non_compliant_stores = total_stores - compliant_stores
    
    # Pie Chart: Ownership Breakdown
    pie_chart = px.pie(df, names="ownershipstatus", title="Store Ownership Distribution")
    
    # Bar Chart: Stores by City
    city_counts = df["city"].value_counts().reset_index()
    city_counts.columns = ["City", "Store Count"]
    bar_chart = px.bar(city_counts, x="City", y="Store Count", title="Stores by City")
    
    # Data Table
    data_table = dash_table.DataTable(
        columns=[{"name": i, "id": i} for i in df.columns],
        data=df.to_dict("records"),
        page_size=10,
        style_table={"overflowX": "auto"}
    )
     
    # Check if the DataFrame is empty
    if df.empty:
        logging.warning("DataFrame is empty. No data available for dashboard.")

    return dbc.Container([
        html.H1("Store Details Dashboard", className="text-center mt-4"),
        
        # Key Metrics
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([html.H3("Total Stores"), html.P(total_stores)]), color="primary", inverse=True), width=4),
            dbc.Col(dbc.Card(dbc.CardBody([html.H3("Compliant Stores"), html.P(compliant_stores)]), color="success", inverse=True), width=4),
            dbc.Col(dbc.Card(dbc.CardBody([html.H3("Non-Compliant Stores"), html.P(non_compliant_stores)]), color="danger", inverse=True), width=4),
        ], className="mt-4"),
        
        # Charts
        dbc.Row([
            dbc.Col(dcc.Graph(figure=pie_chart), width=6),
            dbc.Col(dcc.Graph(figure=bar_chart), width=6),
        ], className="mt-4"),
        
        # Data Table
        html.H2("Store Details", className="mt-4"),
        dbc.Card(dbc.CardBody([data_table]))
    ], fluid=True)


# function to get storage client 



#define a function to generate a signed URL ( this should in the future be moved to utils.py
def generate_signed_url(bucket_name, blob_name, expiration=3600):
    """Generate a signed URL for secure temporary access to a file in GCS."""
    storage_client = get_storage_client()  # Fetch storage client
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        expiration=timedelta(seconds=expiration),  # Expires in 1 hour
        method="GET"
    )
    return url


def get_access_token(id_token=None):
    """Get access token from STS exchange using Azure ID token."""
    if id_token:
        return exchange_id_token_for_access_token(id_token)

    # Use access token from session
    access_token = session.get("google_access_token")
    if not access_token:
        raise Exception("No access token found in session.")
    
    return access_token




def generate_temporary_download_url(bucket_name, blob_name, access_token):
    """Generate a temporary download URL for a GCS object using an access token."""
    # Construct the GCS API URL for the object
    url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"

    # Set the Authorization header with the access token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Make a GET request to the GCS API
    response = requests.get(url, headers=headers, stream=True)

    if response.status_code == 200:
        # Return the direct download URL
        return url
    else:
        # Handle errors
        print(f"Error fetching file: {response.status_code} - {response.text}")
        return None
    


# helper function to handle loading of different environment files for store, official and admin apps
# utils/env_loader.py


def load_env(app_name: str):
    dotenv_file = f".env.preprod.{app_name}"
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "env", dotenv_file)
    full_path = os.path.abspath(dotenv_path)

    print(f"📍 Loading environment for: {app_name}")
    print(f"🧾 Full path: {full_path}")
    if not os.path.exists(full_path):
        print(f"❌ Error: {dotenv_file} not found at {full_path}")
        sys.exit(1)

    load_dotenv(dotenv_path=full_path, verbose=True)




