from core import naledi_bp                                                                                                                 # Import the naledi blueprint
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app,Flask
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from core.naledimodels import UserProfile, User, StoreDetails, SpazaOwner,RegistrationForm, Document, MncUser                           # Import the User model
from .utils import is_valid_email, is_valid_cellno, is_valid_password, generate_dashboard_layout,fetch_data, set_password,check_password                                                 # Import from utils.py
from core import oauth,user_login_manager
#from .oauth import oauth,user_login_manager,setup_azure_oauth                                                                                                       # Import the OAuth instance from naledi/__init__.py
from core import db, mail
from google.oauth2 import id_token   
from msal import PublicClientApplication
import requests
import os
import jwt 
from jwt.exceptions import InvalidTokenError                                                                                               # Import the InvalidTokenError class
from itsdangerous import SignatureExpired, BadSignature
from flask_mailman import EmailMessage                                                                                                     # Import the Mail class and EmailMessage class
from core.utils import authenticate_ad_user
from flask import jsonify
import dash
import dash_bootstrap_components as dbc
from core.utils import generate_dashboard_layout  # Import function
import plotly.express as px  # ✅ Import Plotly Express for charts
import secrets
import smtplib
import re
from functools import wraps
from core.oauth_setup import setup_azure_oauth


# testing this option
#naledi_bp = Blueprint('naledi_bp', __name__,url_prefix='/naledi',template_folder="templates",static_folder="static")                                                                                   # Create the naledi blueprint



google = oauth.create_client('google')  # create the google oauth client

# This is the decorator for the progress . it is not suiatble here but will put in anyway since this route is tightlu linked to spachain auth

@naledi_bp.context_processor
def inject_progress():
    if current_user.is_authenticated:
        return {"progress": get_registration_progress(current_user.user_id)}
    return {"progress": {
        "profile_complete": "not-started",
        "registration_complete": "not-started",
        "store_details_complete": "not-started",
        "documents_uploaded": "not-started"
    }}



# Regular store user loader

@user_login_manager.user_loader
def load_user(user_id):
    user = UserProfile.query.get(user_id)
    if user:
        print(f"User loaded: {user.username}")
        return user

def user_required(f):
    """Ensure that the user is an authenticated normal user (not an admin or official)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in first.", "warning")
            return redirect(url_for('naledi.naledi_login'))  # Redirect to normal user login

        # Ensure user is NOT an admin or an official (MncUser)
        if isinstance(current_user, MncUser):
            flash("Unauthorized access.", "error")
            return redirect(url_for('admin.admin_dashboard'))  # Redirect to admin panel

        return f(*args, **kwargs)
    
    return decorated_function



# Function to verify Google token
def verify_google_token(id_token):
    try:
        # Decode token WITHOUT verifying the signature (for debugging)
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        print("Decoded Google ID Token:", decoded_token)

        # Ensure the 'iss' (issuer) claim is valid
        if decoded_token.get("iss") not in ["https://accounts.google.com", "accounts.google.com"]:
            raise ValueError(f"Invalid issuer: {decoded_token.get('iss')}")

        return decoded_token
    except InvalidTokenError:
        print("Invalid token received from Google.")
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None 

# login mnager for authenticating the user. 
# extend the login manager to include the admin user , and later the offcial user
# login manager for the admin user

@naledi_bp.route('/')
def landing_page():
    # If user is authenticated, fetch progress
    progress = None
    if current_user.is_authenticated:
        progress = get_registration_progress(current_user.user_id)
        print("Rendering the landing page with progress:", progress)
        return render_template("naledibase.html", user=current_user, progress=progress)
    return render_template("naledi_home.html", user=current_user,progress=progress)    
    #render_template("naledi_home.html", user=current_user, progress=progress)


# Main login route for for store users 
@naledi_bp.route('/naledi_login', methods=['GET', 'POST'])
def naledi_login():
    """Handles login for Naledi users, without admin/MncUser checks."""

    print("Reached Naledi Login route.")

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Ensure email is provided
        if not email:
            flash('Email is required.', category='error')
            return render_template("naledi_login.html", user=current_user)

        # Fetch user by email
        user = UserProfile.query.filter_by(email=email).first()

        if user:
            # ✅ Check if the user is a Google user
            if user.is_social_login_user:
                flash(
                    'This account uses Google Sign-In. Please use the "Sign in with Google" button.',
                    category='info'
                )
                return render_template(
                    "naledi_login.html",
                    user=current_user,
                    is_social_login_user=True,
                    google_login_url=url_for('naledi.google_auth')
                )

            # ✅ Validate password for standard users
            if check_password_hash(user.user_password, password):
                login_user(user, remember=True)
                flash('Logged in successfully!', category='success')
                return redirect(url_for('naledi.naledi_home'))
            else:
                flash('Invalid password. Please try again.', category='error')
        else:
            flash('No account found with this email.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))

    # ✅ Google login URL for GET requests or after errors
    google_login_url = url_for('naledi.google_auth', _external=True)

    # ✅ Render the login form
    return render_template( "naledi_login.html", user=current_user, is_social_login_user=False, google_login_url=google_login_url , progress=None)


# route to handle forgot forgot password and reset for store users
@naledi_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def naledi_reset_password(token):
    user = UserProfile.verify_reset_token(token)
    if not user:
        flash('Invalid or expired token.', 'error')
        return redirect(url_for('naledi.naledi_forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate password complexity
        if not is_valid_password(new_password):
            flash('Password must include at least 8 characters, one uppercase letter, one lowercase letter, one digit, and one special character.', 'error')
            return redirect(url_for('naledi.naledi_reset_password', token=token)) 

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('naledi.naledi_reset_password', token=token))

        # ✅ Set new password and commit
        user.set_password(new_password)
        db.session.commit()

        flash('Password reset successful! You can now log in.', 'success')
        return redirect(url_for('naledi.naledi_login'))  # Or your preferred login page

    return render_template('naledi_reset_password.html', token=token)


# ✅ Admin Forgot Password
@naledi_bp.route('/forgot_password', methods=['GET', 'POST'])
def naledi_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = UserProfile.query.filter_by(email=email).first()

        if not user:
            flash('No account found with this email.', 'error')
            return redirect(url_for('naledi.naledi_forgot_password'))
        
        if user.is_social_login_user:
            flash('This account uses Google Sign-In. Please reset your password via Google.', 'error')
            return redirect(url_for('naledi.naledi_login'))
       
        # Generate reset token and create the reset link

        reset_token = user.generate_reset_token()
        reset_url = url_for('naledi.naledi_reset_password', token=reset_token, _external=True)
       

          # ✅ Create Email Message (Correct Flask-Mailman Syntax)
        msg = EmailMessage(
            subject="Password Reset Request",
            body=f"Click the link below to reset your password:\n{reset_url}",
            from_email=current_app.config['MAIL_DEFAULT_SENDER'],
            to=[user.email]  # Must be a list
        )

        # ✅ Send the email
        msg.send()  # Flask-Mailman sends the email directly

        """ try:
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(current_app.config['MAIL_DEFAULT_SENDER'], current_app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            flash('Password reset link sent.', 'success')
        except Exception as e:
            flash(' 🚫 Error sending password reset email.', 'error') """

        flash('If your email exists in our system, you will receive a reset link.', 'info')
        return redirect(url_for('naledi.naledi_login'))
    
    progress = {
    "profile_complete": "not-started",
    "registration_complete": "not-started",
    "store_details_complete": "not-started",
    "documents_uploaded": "not-started"
     }    

    return render_template('naledi_forgot_password.html',progress = progress)

# Route to handle the landing page for the store users
@naledi_bp.route('/naledi_home')
@login_required
def naledi_home():
    
    print("Reached Naledi Home route.")

     # Ensure non-admin users land here
    """ if isinstance(current_user, MncUser) and current_user.is_admin:
        print(" Admin cannot access Naledi Home. Redirecting.")
        return redirect(url_for("admin.admin_dashboard")) 
    """


    spaza_owner = SpazaOwner.query.filter_by(user_profile_id=current_user.user_profile_id).first()
    
    # Initialize store variable to None as a fallback
    store = None
    progress = get_registration_progress(current_user.user_profile_id)  # Fetch progress data ✅
    verifications = None

    if spaza_owner:
        
        # Query for the store details
        store = StoreDetails.query.filter_by(owner_id=spaza_owner.owner_id).first()
        
        if store:
            # Check for both registered and draft statuses
            if store.reg_status == 'registered' or store.reg_status == 'draft': 
                print("Store has been registered or is in draft status")
                current_user.has_registered_store = True
                if store.reg_status == 'registered':
                    flash('You have already registered your store!', category='success')
                else:
                    flash('Your store is in draft status. Please complete the registration.', category='info')
            else:
                current_user.has_registered_store = False
                flash('Your store registration is pending or in an unknown status.', category='warning')
        else:
            # If store is not found, handle this case too
            current_user.has_registered_store = False
            flash('No store registered!', category='warning')
    else:
        current_user.has_registered_store = False

    return render_template("spachainauth_home.html", user=current_user, store=store, progress=progress,verifications=verifications)  # ✅ Pass progress


@naledi_bp.route('/services')
#@login_required
def naledi_services():
    return render_template("naledi_services.html", user=current_user)

# Unified login/sign-up route
@naledi_bp.route('/auth/google')
def google_auth():
    redirect_uri = url_for('naledi.google_callback', _external=True)
    #print("Google Redirect URI:", redirect_uri)
    return google.authorize_redirect(redirect_uri)

# Callback route for Google OAuth
@naledi_bp.route('/auth/google/callback')
def google_callback():
    
    print("Google Callback route reached.")
    print("re redirect URI:", request.url)  
    
    try:
        # Fetch token and user info from Google
        #print("Google Callback route reached.")
        #print("Trying to inspect the token")
        token = google.authorize_access_token()
       # print("Raw Google Token:", token)
        id_token = token['id_token']

        if not token:
           raise ValueError("No token received from Google.")

        if 'id_token' not in token:
           raise ValueError(f"Missing ID token. Full response: {token}")

        # Verify Google ID Token before proceeding
        verified_token = verify_google_token(id_token)
        if not verified_token:
            flash("Invalid Google authentication token.", category="error")
            return redirect(url_for("naledi.naledi_login"))


        user_info = google.get('userinfo').json()
       
       # print("Google User Info:", user_info)

        email = user_info.get('email')
        name = user_info.get('name')

        # Check if the user exists
        existing_user = UserProfile.query.filter_by(email=email).first()
        if existing_user:
           login_user(existing_user)
           flash("Logged in successfully!", category="success")
           return redirect(url_for('naledi.naledi_home'))

        else:
            # Create a new user if they don’t exist
              new_user = UserProfile(
                username=name,
                email=email,
                cellno='000-000-000',  # Default value for Google users
                user_password='N/A',  # Default value for Google users
                is_social_login_user=True
                 )
              db.session.add(new_user)
              db.session.commit()
              login_user(new_user)
              flash('login with Google successful!', category='success')
        return redirect(url_for('naledi.naledi_home'))
        
    except Exception as e:
        print(f"Error during Google callback: {e}")
        flash('An error occurred during Google authentication.', category='error')
        return redirect(url_for('naledi.naledi_login'))


# Standard sign-up process for users without Google OAuth
@naledi_bp.route('/naledi_sign_up', methods=['GET', 'POST'])
def naledi_sign_up():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        email = request.form.get('email')
        cellno = request.form.get('cellno')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        print(f"Sign-up form submitted: {first_name}, {email}, {cellno}")

        # Check if the email or cell number already exists
        user = UserProfile.query.filter(
            (UserProfile.email == email) | (UserProfile.cellno == cellno)
        ).first()

        if user:
            flash('Email or cell number already exists.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))

        elif not is_valid_email(email):
            flash('Invalid email format.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))

        elif not is_valid_cellno(cellno):
            flash('Provide a valid South African cell number.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))

        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))

        elif not is_valid_password(password1):
            flash('Password must include at least 8 characters, one uppercase letter, one lowercase letter, one digit, and one special character.', category='error')
            return redirect(url_for('naledi.naledi_sign_up'))
        else:
            # Create a new user with verification pending
            new_user = UserProfile(
                username=first_name,
                email=email,
                cellno=cellno,
                user_password=generate_password_hash(password1, method='pbkdf2:sha256'),
                is_social_login_user=False,                                              # Explicitly set this to False
                user_type='spaza_user',
                is_verified=False                                                         # New field for email verification
            )

            #print(f"confirmation URL : {confirm_url}")

            try:
                db.session.add(new_user)
                db.session.commit()
                print("User added successfully.")
                
                # Generate email verification token
                #print(f"serilizer: {current_app.serializer}")
            # ✅ Generate email verification token BEFORE creatin

                token = current_app.serializer.dumps(email, salt='email-confirm')

                confirm_url = url_for('naledi.confirm_email', token=token, _external=True)
                
                  # Create an email message
                #print("testing with email message")  
                msg = EmailMessage(
                      subject="Confirm Your Email baba!",
                      body=f"Click the link to confirm your email: {confirm_url}",
                      from_email=current_app.config['MAIL_DEFAULT_SENDER'],
                      to=[email],  # Replace with your email address
                       )

                msg.send()  # Send the email
                flash('A verification email has been sent. Please check your inbox.', category='info')
            except Exception as e:
                db.session.rollback()
                print(f"Error adding user: {e}")
                flash('An error occurred during sign-up.', category='error')
                return redirect(url_for('naledi.naledi_sign_up'))  
            
    google_login_url = url_for('naledi.google_auth', _external=True) 
    return render_template('naledi_sign_up.html', user=current_user, google_login_url=google_login_url)
    
@naledi_bp.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = current_app.serializer.loads(token, salt='email-confirm', max_age=3600)  # Token expires in 1 hour
        print(f"Decoded email from token: {email}")
    except  (SignatureExpired, BadSignature):
        flash('The confirmation link is invalid or has expired.', 'error')
        return redirect(url_for('naledi.naledi_sign_up'))

    user = UserProfile.query.filter_by(email=email).first()
    if user:
        user.is_verified = True
        db.session.commit()
        flash('Account has been  verified! Please log in.', category='success')
        return redirect(url_for('naledi.naledi_login'))
    else:
        flash('No user found. Please sign up.', category='error')
    return redirect(url_for('naledi.naledi_sign_up'))


# define the function to get the registration status

def get_registration_progress(user_id):
    progress = {
        "profile_complete": False,
        "registration_complete": False,
        "store_details_complete": False,
        "documents_uploaded": False,
    }

    # Check if profile is complete
    user_profile = UserProfile.query.filter_by(user_id=user_id).first()
    if user_profile:
        progress["profile_complete"] = True

    # Check if registration form is submitted
    reg_form = RegistrationForm.query.filter_by(user_id=user_id).first()
    if reg_form:
        progress["registration_complete"] = True

    # Check if store details are submitted
    store_details = StoreDetails.query.filter_by(owner_id=user_id).first()
    if store_details:
        progress["store_details_complete"] = True

    # Check if documents are uploaded
    documents = Document.query.filter_by(uploaded_by_user_id=user_id).first()
    if documents:
        progress["documents_uploaded"] = True

    return progress

# the route to manage registration status from profile registtation to Documents upload

@naledi_bp.route('/registration_progress', methods=['GET', 'POST'])
@login_required
def naledi_registration_progress():
    user_id = current_user.user_id

    # Get the registration progress
    progress = get_registration_progress(user_id)
    print(f"Registration Progress: {progress}")

    # Redirect if any step is incomplete
    if not progress["profile_complete"]:
        flash('No user profile found. Please complete your profile first.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))
    if not progress["registration_complete"]:
        flash('No registration form found. Please complete registration form first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_register', user_id=user_id))
    if not progress["store_details_complete"]:
        flash('No store details found. Please complete store details first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_store', user_id=user_id))
    if not progress["documents_uploaded"]:
        flash('No documents found. Please upload documents first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_upload_docs', user_id=user_id))

    # If all steps are complete, render the progress bar
    return render_template('spachainauth_home.html',user=current_user ,progress=progress)




"""@naledi_bp.route('/naledi_welcome')
def naledi_welcome():
    return render_template("naledi_welcome.html")"""

@naledi_bp.route('/naledi_howner')
def naledi_howner():
    return render_template("naledi_howner.html")

@naledi_bp.route('/naledi_hstore')
def naledi_hstore():
    return render_template("naledi_hstore.html")

@naledi_bp.route('/naledi_hcomp')
def naledi_hcomp():
    return render_template("naledi_hcomp.html")

@naledi_bp.route('/naledi_hmnc')
def naledi_hmnc():
    return render_template("naledi_hmnc.html")




"""@naledi_bp.route('/check_registration_status')
def check_registration_status():
    # Query the store registration status
    store = StoreDetails.query.filter_by(owner_id=current_user.id).first()

    print("checking store registration status")

    if store:
        if store.reg_status == 'registered':  # You can adjust this condition as per your criteria
            current_user.has_registered_store = True

        else:
            current_user.has_registered_store = False
    else:
        current_user.has_registered_store = False
    
    return redirect(url_for('naledi.naledi_home'))  # Or wherever you need to redirect """


@naledi_bp.route('/logout')
@login_required
def naledi_logout():
    logout_user()
    flash('Logged out successfully.', category='success')
    return redirect(url_for('naledi.naledi_login'))


@naledi_bp.route('/mnclist')
def naledi_mnclist():

    #return render_template("naledi_mnc_list.html")
    return render_template("naledi_hmnc.html")


# The real azure call back route
from flask import request, session

# Redundant v- this route is not used as offcicials are signed up by the admin in the municipality.
# The offcial sign-up process for the municipal / official users. 
@naledi_bp.route('/official/signup', methods=['POST'])
def official_sign_up():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        email = request.form.get('email')
        municipality = request.form.get('municipality')
        department = request.form.get('department')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        # Validate email (must be a municipality email)
        if not email.endswith('.gov'):
            flash('Please use an official municipality email address.', 'error')
            return redirect(url_for('naledi.official_sign_up'))

        # Check if the email already exists
        if MncUser.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('naledi.official_sign_up'))

        # Validate passwords
        if password1 != password2:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('naledi.official_sign_up'))

        # Create a new official user
        new_user = MncUser(
            first_name=first_name,
            email=email,
            municipality=municipality,
            department=department,
            password=generate_password_hash(password1, method='pbkdf2:sha256'),
            is_verified=False
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('naledi.official_login'))

    return redirect(url_for('naledi.official_sign_up',user=current_user))



#define the route for offcial services    
@naledi_bp.route('/official_services')
#@login_required
def official_services():
    return render_template("official_services.html", user=current_user)


#route the enable reset  password. 
@naledi_bp.route('/official/reset_password/<token>', methods=['GET', 'POST'])
def official_reset_password(token):
    user = MncUser.verify_reset_token(token)

    if not user:
        flash('Invalid or expired token.', 'error')
        return redirect(url_for('naledi.official_forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('naledi.official_reset_password', token=token))

        # Update password and remove reset token
        user.save_password(new_password)

        flash('Password reset successful! You can now log in.', 'success')
        return redirect(url_for('naledi.official_login'))

    return render_template('official_reset_password.html', token=token)


# define the route to enable password reset
@naledi_bp.route('/official/forgot_password', methods=['GET', 'POST'])
def official_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = MncUser.query.filter_by(mncemail=email).first()

        if not user:
            flash('No account found with this email.', 'error')
            return redirect(url_for('naledi.official_forgot_password'))

        if user.is_sso_only:
            flash('This account uses Microsoft SSO. Please reset your password via Azure AD.', 'error')
            return redirect(url_for('naledi.official_login'))

        # Generate reset token and create the reset link
        reset_token = user.generate_reset_token()
        reset_url = url_for('naledi.official_reset_password', token=reset_token, _external=True)

        # Create EmailMessage
        msg = EmailMessage()
        msg["Subject"] = "Password Reset Request"
        msg["From"] = current_app.config['MAIL_DEFAULT_SENDER']
        msg["To"] = email
        msg.set_content(f"""
        Hello {user.mncfname},

        A request to reset your password has been made. Click the link below to reset your password:

        {reset_url}

        If you did not request this, please ignore this email.

        This link is valid for 1 hour.

        Best regards,
        The Team
        """)

        # Send email via SMTP
        try:
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                server.starttls()  # Secure connection
                server.login(current_app.config['MAIL_DEFAULT_SENDER'], current_app.config['MAIL_PASSWORD'])
                server.send_message(msg)

            flash('A password reset link has been sent to your email.', 'success')
        except Exception as e:
            print(f"Error sending email: {e}")
            flash('Error sending password reset email. Please try again later.', 'error')

        return redirect(url_for('naledi.official_login'))

    return render_template('official_forgot_password.html')




# The route to validate registration of an official user
@naledi_bp.route('/official/register/<token>', methods=['GET', 'POST'])
def official_register(token):
    """Handles pre-registered user registration."""
    user = MncUser.verify_reset_token(token)  # Use token verification

    if not user:
        flash('Invalid or expired registration link.', 'error')
        return redirect(url_for('naledi.official_login'))

    if request.method == 'POST':
        # Get form data
        municipality = request.form.get('municipality')
        department = request.form.get('department')
        job_title = request.form.get('job_title')
        contact = request.form.get('contact')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate passwords match
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('naledi.official_register', token=token))

        # Update user information
        user.municipality = municipality
        user.department = department
        user.mnc_title = job_title
        user.mnc_contact = contact
        user.save_password(password)  # Hash and store new password
        user.is_verified = True  # Mark as verified
        user.is_sso_only = True  # Enforce SSO after first login
        db.session.commit()

        flash('Registration complete! Use Microsoft SSO for future logins.', 'success')
        return redirect(url_for('naledi.official_azure_login'))

    return render_template('official_register.html', user=user, token=token)



# generate a dashboard to show spazalytics
def create_dashboard(flask_app):
    """Initialize Dash inside the correct app context"""
    with flask_app.app_context():
        dashboard_app = dash.Dash(
            __name__,
            server=flask_app,
            url_base_pathname="/naledi/official/dashboard/",
            external_stylesheets=[dbc.themes.BOOTSTRAP]
        )
        dashboard_app.layout = generate_dashboard_layout()
        return dashboard_app



@naledi_bp.route('/official_dashboard')
def official_dashboard():
    print("Reached the official dashboard route.")
    #return render_template("official_dashboard.html")   
    
    df = fetch_data()
  
    print("fetching the data")
     
    # Generate Dash components
    pie_chart = px.pie(df, names="ownershipstatus", title="Store Ownership Distribution").to_html()
    bar_chart = px.bar(df, x="city", y="store_name", title="Stores by City").to_html()
    
    # Convert DataFrame to HTML table
    data_table = df.to_html(classes="table table-striped table-bordered", index=False)

    return render_template(
        "official_dashboard.html",
        pie_chart=pie_chart,
        bar_chart=bar_chart,
        data_table=data_table,
        total_stores=len(df),
        compliant_stores=len(df[df["compstatus"] == "Compliant"]),
        non_compliant_stores=len(df[df["compstatus"] != "Compliant"]),
    )




# this section must be moved to other approapriate modules 

@naledi_bp.route('/official/azure/login')
def official_azure_login():
    """Redirect to Azure AD for authentication."""
    print("Reached the Azure login route")

    # Construct the correct redirect URI
    redirect_uri = request.host_url.rstrip('/') + url_for('naledi.official_azure_callback', _external=False)
    redirect_uri = redirect_uri.replace("127.0.0.1", "localhost")
    print("Azure Redirect URI:", redirect_uri)

    # Generate and store the state in session
    state = azure.create_authorization_url(redirect_uri)['state']
    session['oauth_state'] = state  # Store in session before redirecting

    print(f"Generated OAuth State: {state}")

    return azure.authorize_redirect(redirect_uri, state=state)

    
# define an official azure call back route
@naledi_bp.route('/official/azure/callback')
def official_azure_callback():
    """Handle Azure AD callback."""
    print("Reached the Azure AD callback route.")

    try:
        # Retrieve state from session
        expected_state = session.pop('oauth_state', None)
        received_state = request.args.get('state')

        print(f"Expected State: {expected_state}, Received State: {received_state}")

        # Validate state
        if not expected_state or expected_state != received_state:
            raise ValueError("CSRF Warning! State not equal in request and response.")

        # Fetch token from Azure AD
        token = azure.authorize_access_token()
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        # Use Microsoft Graph API to get user info
        user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers).json()

        email = user_info.get('mail') or user_info.get('userPrincipalName')
        name = user_info.get('displayName')

        if not email:
            flash('Azure authentication failed: No email received.', category='error')
            return redirect(url_for('naledi.official_login'))

        # Check if user exists in the database
        user = MncUser.query.filter_by(mncemail=email).first()
        if user:
            login_user(user)
            flash('Logged in successfully!', 'success')
        else:
            new_user = MncUser(
                mncfname=name.split(" ")[0],
                mnclname=" ".join(name.split(" ")[1:]),
                mncemail=email,
                municipal_id=0,  # Set default, can be updated later
                dept_id=0,  # Set default, can be updated later
                password_hash=None,  # No password needed for SSO users
                is_verified=True,
                is_sso_only=True
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Account created and logged in successfully!', 'success')

        return redirect(url_for('naledi.naledi_home'))

    except Exception as e:
        print(f"Error during Azure AD callback: {e}")
        flash('An error occurred during Azure AD authentication.', category='error')
        return redirect(url_for('naledi.official_login'))

