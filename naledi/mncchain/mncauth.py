from naledi.mncchain import mncauth
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_required, current_user, LoginManager, logout_user,login_user
from core.naledimodels import db, MncUser, UserProfile, Municipal, MncDepartment
from core.utils import set_password, check_password, verify_reset_token,exchange_id_token_for_access_token
#from admin_utils import send_registration_email  # Import email function
from flask_mailman import EmailMessage 
from functools import wraps
from core.oauth_setup import verify_azure_token
from itsdangerous import SignatureExpired, BadSignature
import smtplib
import re, os
import jwt, requests
from werkzeug.security import check_password_hash
from core import  official_login_manager, exchange_id_token_for_access_token
  
# This blueprint is dedicated to user manangement for azure routes ( admin and offical users)


mncauth = Blueprint('mncauth', __name__,url_prefix='/mncauth',template_folder='templates')  # ✅ Explicitly set template folder)


# user loader define for the official user
"""@official_login_manager.user_loader
def load_official(user_id):
    
    print(f"🔹 Loading official User: {user_id}")

    # debug statement
    if not user_id:
        print("❌ `user_id` is None! This means Flask-Login did not pass a valid ID.")
        return None
    
    try:
        user_id = int(user_id)  # Ensure it's an integer
    except ValueError:
        print(f"❌ Invalid user_id format: {user_id}")
        return None
"""


@official_login_manager.user_loader
def load_official(user_id):
    """Loads an offcial  user from the database using Flask-Login."""
    print(f"🔹 Loading official User: {user_id}")

    # Query using mnc_user_id instead of default id
    user = MncUser.query.get(int(user_id))  # ✅ Use `id` instead of `mnc_user_id`

    print(f"🔹 User: {user}" )
    #print(f"🔹 is this an official ? : {user.is_official}" )


    if user and user.is_official:
        print(f"✅ official User Loaded: {user.mncfname} {user.mnclname}")
        return user

    print(f"🚨 User {user_id} is not an admin or does not exist!")
    return None  # Return None if not an admin


# ✅ Ensure only authenticated Offcials can access routes
def official_required(f):
    """Ensure the user is an authenticated admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"🔹 Checking admin access for user: {current_user}")

        print(f"🔹 User is authenticated: {current_user.is_authenticated}")

        if not current_user.is_authenticated:
            print("❌ User is NOT authenticated. Redirecting to login.")
            flash("Please log in first.", "warning")
            return redirect(url_for('mncauth.official_login'))

        if not isinstance(current_user, MncUser):
            print("❌ User is not an instance of MncUser.")
            flash("Unauthorized access.", "error")
            return redirect(url_for('mncauth.official_login'))

        if not current_user.is_official:
            print("❌ User is not an official.")
            flash("You do not have offcial  privileges.", "error")
            return redirect(url_for('mncauth.official_login'))

        print("✅ offcial  check passed.")
        return f(*args, **kwargs)
    
    return decorated_function


# Offcial  home route
@mncauth.route('/home')
#@login_required
#@official_required
def official_home():
    """Ensure only admins access this, and clear session if switching user types."""
    print(f"🏠 Reached offcial home. Current user: {current_user}")

    if current_user.is_authenticated:
        print(f"🔍 Current User Type Before Redirect: {type(current_user)}")

        # If the logged-in user is NOT an instance of MncUser, they are from store login
        if not isinstance(current_user, MncUser) or not current_user.is_official:
            print("🚨 User is not an official! Logging out and forcing official login.")
            
            logout_user()  # ✅ Clear current user
            session.clear()  # ✅ Force Flask-Login to reset user session

            flash("You need to log in as verified municipal official.", "warning")
            return redirect(url_for("mncauth.official_login"))  # Redirect to admin login

        # ✅ If already an offcial , proceed to the dashboard
        print("🚀 Redirecting official to dashboard.")
        #return redirect(url_for("mncview.official_dashboard"))
        #return redirect(url_for('mncview.official_store_dashboard'))
        return redirect(url_for('mncview.official_view_home'))

    print("🔒 Redirecting user to admin login.")
    return redirect(url_for("mncauth.official_login"))
    


# load the admin_manager and load_user for the admin user
# ✅ Admin Login
@mncauth.route('/login', methods=['GET', 'POST'])
def official_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email:
            flash("Please enter your registered email.", "error")
            return redirect(url_for('mncauth.official_login'))

        # Fetch official from database
        official = MncUser.query.filter_by(mncemail=email).first()

        if not official:
            flash("This email is not registered as an official.", "error")
            return redirect(url_for('mncauth.official_login'))

        # Ensure the official is verified
        if not official.is_verified:
            flash("Your account is not verified. Please check your email.", "warning")
            return redirect(url_for('mncauth.official_login'))

        # OPTION 1: Use Azure AD if it's an enterprise email
        if email.endswith('.gov.za') or email.endswith('.org'):
            session['admin_email'] = email
            return redirect(url_for('mncauth.official_azure_login'))

        # OPTION 2: Use normal email/password login for non-enterprise emails
        if not password:
            flash("Please enter your password.", "error")
            return redirect(url_for('mncauth.official_login'))

        # Validate password
        if not check_password_hash(official.password_hash, password):
            flash("Invalid credentials. Please try again.", "error")
            return redirect(url_for('mncauth.official_login'))

        # Log in the official
        login_user(official)
        flash("Login successful!", "success")

        # Redirect to official home/dashboard
        return redirect(url_for('mncview.official_store_dashboard'))

    return render_template('official_login.html')

# ✅ Admin Logout
@mncauth.route('/logout')
@login_required
def official_logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('mncauth.official_login'))

# ✅ Azure AD Login for Admins
@mncauth.route('/azure/login')
def official_azure_login():
    """Redirect to Azure AD for authentication."""
    print("🔹 Reached Azure official Login Route")

    # Construct the correct redirect URI
    redirect_uri = request.host_url.rstrip('/') + url_for('mncauth.official_azure_callback', _external=False)
    redirect_uri = redirect_uri.replace("127.0.0.1", "localhost")
    print("Azure Redirect URI:", redirect_uri)

    # Generate and store the state securely in Flask session
    auth_url_data = azure.create_authorization_url(redirect_uri)
    state = auth_url_data.get('state')

    if not state:
        print("⚠️ Warning: OAuth state was not generated correctly!")
        flash('An error occurred during authentication. Please try again.', 'error')
        return redirect(url_for('mncauth.official_login'))  # Redirect to login page

    # ✅ Store state in session before redirecting
    session['oauth_state'] = state
    session.modified = True  # Ensure session is saved
    print(f"✅ Stored OAuth State: {session['oauth_state']}")

    # Redirect to Azure AD for authentication
    return azure.authorize_redirect(redirect_uri, state=state)

# ✅ Azure AD Callback


@mncauth.route('/azure/callback')
def official_azure_callback():
    """Handle Azure AD Official callback."""
    print("🔹 Reached Azure official AD Callback")

    try:
        expected_state = session.pop('oauth_state', None)
        received_state = request.args.get('state')

        print(f"✅ Expected State: {expected_state}, Received State: {received_state}")

        if not expected_state or expected_state != received_state:
            print("🚨 CSRF Warning! State does not match.")
            flash('Security error: Invalid state. Please try again.', 'error')
            return redirect(url_for('mncauth.official_login'))

        token = azure.authorize_access_token()
        if not token:
            print("⚠️ Failed to fetch token from Azure AD.")
            flash('Failed to fetch token from Azure AD. Please try again.', 'error')
            return redirect(url_for('mncauth.official_login'))

        print(f"🔐 Azure Token Response: {token}")  # Optional: Debug log

        gcp_audience = os.getenv("GCP_AUDIENCE")
        print(f"✅ GCP Audience Loaded inside azure callback: {gcp_audience}")

         #✅ Store Azure ID token in session for GCP access later
        id_token = token.get('id_token')
        if id_token:
            session['azure_id_token'] = id_token
            print("✅ Azure ID token stored in session.")

            # 🆕 Exchange for Google access token now and store it
            try:
                google_access_token = exchange_id_token_for_access_token(id_token)
                session['google_access_token'] = google_access_token
                print("✅ Google access token stored in session.")
            except Exception as e:
                print(f"❌ Token exchange failed during callback: {e}")
                flash('Authentication error during token exchange.', 'error')
                return redirect(url_for('mncauth.official_login'))

        else:
            print("❌ No ID token received from Azure!")
            flash('Authentication error: No ID token received.', 'error')
            return redirect(url_for('mncauth.official_login'))


        # Fetch user info using access_token
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers).json()
        print("🔹 Azure AD User Info:", user_info)

        email = user_info.get('mail') or user_info.get('userPrincipalName')

        if not email:
            print("❌ Azure authentication failed: No email received.")
            flash('Azure authentication failed: No email received.', 'error')
            return redirect(url_for('mncauth.official_login'))

        if "#EXT#" in email:
            match = re.search(r"(.+?)_([^#]+)#EXT#@", email)
            if match:
                email = match.group(1).replace("_", ".") + "@" + match.group(2)
        
        print(f"✅ Processed Email: {email}")

        user = MncUser.query.filter_by(mncemail=email).first()
        
        if user:
            login_user(user)
            session.modified = True
            print(f"✅ O tsene lenyora: {email}")
            flash('Logged in successfully as Admin!', 'success')
            return redirect(url_for('mncview.official_dashboard'))  # You can use official_doc_dashboard too
        else:
            print(f"❌ Unauthorized access attempt: {email}")
            flash('Unauthorized access. Contact the administrator.', 'error')
            return redirect(url_for('mncauth.official_login'))

    except Exception as e:
        print(f"🚨 Error during Azure AD callback: {e}")
        flash('An error occurred during Azure authentication.', 'error')
        return redirect(url_for('mncauth.official_login'))



# ✅ Admin Password Reset
@mncauth.route('/reset_password/<token>', methods=['GET', 'POST'])
def official_reset_password(token):
    """Handles password reset via secure token."""
    user_id = verify_reset_token(token)  # ✅ Now using utils.py function

    if not user_id:
        flash("Invalid or expired reset token.", "error")
        return redirect(url_for('mncauth.official_forgot_password'))

    user = MncUser.query.get(user_id)

    if not user:
        flash("User not found.", "error")
        return redirect(url_for('mncauth.official_forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        token = request.form.get('token')  # ✅ Retrieve token from hidden field

        if not token:
            flash("Missing reset token. Try again.", "error")
            return redirect(url_for('mncauth.official_forgot_password'))

        if not new_password or len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return redirect(url_for('mncauth.official_reset_password', token=token))

        user.set_password(new_password)  # ✅ Uses MncUser method
        db.session.commit()

        flash("Your password has been updated. You can now log in.", "success")
        return redirect(url_for('mncauth.official_login'))

    return render_template('official_reset_password.html', token=token)



@mncauth.route('/forgot_password', methods=['GET', 'POST'])
def official_forgot_password():
    """Allows officials to request a password reset."""
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Please enter your email.', 'error')
            return redirect(url_for('mncauth.official_forgot_password'))

        user = MncUser.query.filter_by(mncemail=email).first()

        if not user:
            flash('No account found with this email.", "error')
            return redirect(url_for('mncauth.official_forgot_password'))

        # ✅ Generate reset token
        reset_token = user.generate_reset_token()
        reset_url = url_for('mncauth.official_reset_password', token=reset_token, _external=True)

        # ✅ Create Email Message (Correct Flask-Mailman Syntax)
        msg = EmailMessage(
            subject="Password Reset Request",
            body=f"Click the link below to reset your password:\n{reset_url}",
            from_email=current_app.config['MAIL_DEFAULT_SENDER'],
            to=[user.mncemail]  # Must be a list
        )

        # ✅ Send the email
        msg.send()  # Flask-Mailman sends the email directly

        flash("Password reset email sent. Check your inbox.", "success")
        return redirect(url_for('mncauth.official_login'))

    return render_template('official_forgot_password.html')


@mncauth.route('/token-catch')
def token_catch():
    return "Token received! Check URL fragment in your browser URL bar."

