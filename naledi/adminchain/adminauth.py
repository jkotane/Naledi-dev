
from naledi.adminchain import adminauth
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_required, current_user, LoginManager, logout_user,login_user
from core.naledimodels import db, MncUser, UserProfile, Municipal, MncDepartment
from core.utils import set_password
#from admin_utils import send_registration_email  # Import email function
from flask_mailman import EmailMessage 
from functools import wraps
from core import admin_manager,user_login_manager
from itsdangerous import SignatureExpired, BadSignature
import smtplib
import re
import jwt, requests
  
# This blueprint is dedicated to user manangement for azure routes ( admin and offical users)

#admin_bp = Blueprint("admin", __name__)

adminauth = Blueprint('adminauth', __name__,url_prefix='/admin',template_folder='templates')  # ✅ Explicitly set template folder)


@admin_manager.user_loader
def load_admin(user_id):
    """Loads an admin user from the database using Flask-Login."""
    print(f"🔹 Loading Admin User: {user_id}")

    user = MncUser.query.filter_by(mnc_user_id=int(user_id)).first()  

    print(f"🔹 User: {user}" )
    print(f"🔹 is User admin? ?: {user.is_admin}" )
    
    if user and user.is_admin:
        print(f"✅ Admin User Loaded: {user.username}")
        return user

    print(f"🚨 User {user_id} is not an admin or does not exist!")
    return None  # Return None if not an admin

# ✅ Ensure only authenticated admins can access routes
def admin_required(f):
    """Ensure the user is an authenticated admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"🔹 Checking admin access for user: {current_user}")

        print(f"🔹 User is authenticated: {current_user.is_authenticated}")

        if not current_user.is_authenticated:
            print("❌ User is NOT authenticated. Redirecting to login.")
            flash("Please log in first.", "warning")
            return redirect(url_for('adminauth.admin_login'))

        if not isinstance(current_user, MncUser):
            print("❌ User is not an instance of MncUser.")
            flash("Unauthorized access.", "error")
            return redirect(url_for('adminauth.admin_login'))

        if not current_user.is_admin:
            print("❌ User is not an admin.")
            flash("You do not have admin privileges.", "error")
            return redirect(url_for('adminauth.admin_login'))

        print("✅ Admin check passed.")
        return f(*args, **kwargs)
    
    return decorated_function


# admin home route
@adminauth.route('/home')
def admin_home():
    """Ensure only admins access this, and clear session if switching user types."""
    print(f"🏠 Reached admin_home. Current user: {current_user}")

    if current_user.is_authenticated:
        print(f"🔍 Current User Type Before Redirect: {type(current_user)}")

        # If the logged-in user is NOT an instance of MncUser, they are from store login
        if not isinstance(current_user, MncUser) or not current_user.is_admin:
            print("🚨 User is not an admin! Logging out and forcing admin login.")
            
            logout_user()  # ✅ Clear current user
            session.clear()  # ✅ Force Flask-Login to reset user session

            flash("You need to log in as an admin.", "warning")
            return redirect(url_for("adminauth.admin_login"))  # Redirect to admin login

        # ✅ If already an admin, proceed to the dashboard
        print("🚀 Redirecting admin to dashboard.")
        return redirect(url_for("admin.admin_dashboard"))

    print("🔒 Redirecting user to admin login.")
    return redirect(url_for("adminauth.admin_login"))


# load the admin_manager and load_user for the admin user
# ✅ Admin Login
@adminauth.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash("Please enter your enterprise email.", "error")
            return redirect(url_for('adminauth.admin_login'))

        if not email.endswith('.gov.za') and not email.endswith('.org'):
            flash("Please use an official government or enterprise email.", "error")
            return redirect(url_for('adminauth.admin_login'))

        session['admin_email'] = email
        return redirect(url_for('adminauth.admin_azure_login'))

    return render_template('admin_login.html')

# ✅ Admin Logout
@adminauth.route('/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('adminauth.admin_login'))

# ✅ Azure AD Login for Admins
@adminauth.route('/azure/login')
def admin_azure_login():
    """Redirect to Azure AD for authentication."""
    print("🔹 Reached Azure Admin Login Route")

    # Construct the correct redirect URI
    redirect_uri = request.host_url.rstrip('/') + url_for('adminauth.admin_azure_callback', _external=False)
    redirect_uri = redirect_uri.replace("127.0.0.1", "localhost")
    print("Azure Redirect URI:", redirect_uri)

    # Generate and store the state securely in Flask session
    auth_url_data = azure.create_authorization_url(redirect_uri)
    state = auth_url_data.get('state')

    if not state:
        print("⚠️ Warning: OAuth state was not generated correctly!")
        flash('An error occurred during authentication. Please try again.', 'error')
        return redirect(url_for('adminauth.admin_login'))  # Redirect to login page

    # ✅ Store state in session before redirecting
    session['oauth_state'] = state
    session.modified = True  # Ensure session is saved
    print(f"✅ Stored OAuth State: {session['oauth_state']}")

    # Redirect to Azure AD for authentication
    return azure.authorize_redirect(redirect_uri, state=state)

# ✅ Azure AD Callback


@adminauth.route('/azure/callback')
def admin_azure_callback():
    """Handle Azure AD admin callback."""
    print("🔹 Reached Azure AD Callback")

    try:
        # Retrieve expected state from session
        expected_state = session.pop('oauth_state', None)  # Remove it after use
        received_state = request.args.get('state')

        print(f"✅ Expected State: {expected_state}, Received State: {received_state}")

        # Ensure state matches
        if not expected_state or expected_state != received_state:
            print("🚨 CSRF Warning! State does not match.")
            flash('Security error: Invalid state. Please try again.', 'error')
            return redirect(url_for('adminauth.admin_login'))

        # Fetch token from Azure AD
        token = azure.authorize_access_token()
        if not token:
            print("⚠️ Failed to fetch token from Azure AD.")
            flash('Failed to fetch token from Azure AD. Please try again.', 'error')
            return redirect(url_for('adminauth.admin_login'))

        # Fetch user info from Microsoft Graph API
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers).json()
        print("🔹 Azure AD User Info:", user_info)

        email = user_info.get('mail') or user_info.get('userPrincipalName')

        if not email:
            print("❌ Azure authentication failed: No email received.")
            flash('Azure authentication failed: No email received.', 'error')
            return redirect(url_for('adminauth.admin_login'))

        # Normalize Azure email format if it contains "#EXT#"
        if "#EXT#" in email:
            match = re.search(r"(.+?)_([^#]+)#EXT#@", email)
            if match:
                email = match.group(1).replace("_", ".") + "@" + match.group(2)
        
        print(f"✅ Processed Email: {email}")

        # Check if user exists in the database
        user = MncUser.query.filter_by(mncemail=email).first()
        
        if user:
            login_user(user)
            session.modified = True
            print(f"✅ O tsene lenyora: {email}")
            flash('Logged in successfully as Admin!', 'success')
            return redirect(url_for('admin.admin_dashboard'))  # Redirect correctly
        else:
            print(f"❌ Unauthorized access attempt: {email}")
            flash('Unauthorized access. Contact the administrator.', 'error')
            return redirect(url_for('adminauth.admin_login'))

    except Exception as e:
        print(f"🚨 Error during Azure AD callback: {e}")
        flash('An error occurred during Azure authentication.', 'error')
        return redirect(url_for('adminauth.admin_login'))


# ✅ Admin Password Reset
@adminauth.route('/reset_password/<token>', methods=['GET', 'POST'])
def admin_reset_password(token):
    user = MncUser.verify_reset_token(token)
    if not user:
        flash('Invalid or expired token.', 'error')
        
        return redirect(url_for('adminauth.admin_forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('adminauth.admin_reset_password', token=token))

        user.save_password(new_password)

        flash('Password reset successful! You can now log in.', 'success')
        return redirect(url_for('adminauth.admin_azure_login'))

    return render_template('admin_reset_password.html', token=token)

# ✅ Admin Forgot Password
@adminauth.route('/forgot_password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = MncUser.query.filter_by(mnc_email=email).first()

        if not user:
            flash('No account found with this email.', 'error')
            return redirect(url_for('adminauth.admin_forgot_password'))

        reset_token = user.generate_reset_token()
        reset_url = url_for('adminauth.admin_reset_password', token=reset_token, _external=True)

        msg = EmailMessage()
        msg["Subject"] = "Password Reset Request"
        msg["From"] = current_app.config['MAIL_DEFAULT_SENDER']
        msg["To"] = email
        msg.set_content(f"Click the link to reset your password: {reset_url}")

        try:
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(current_app.config['MAIL_DEFAULT_SENDER'], current_app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            flash('Password reset link sent.', 'success')
        except Exception as e:
            flash('Error sending password reset email.', 'error')

        return redirect(url_for('adminauth.admin_azure_login'))

    return render_template('admin_forgot_password.html')