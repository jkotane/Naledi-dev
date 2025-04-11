from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from core.naledimodels import db, MncUser, MncDepartment
from functools import wraps
# ✅ Import `adminauth` for authentication
from naledi.adminchain.adminauth import adminauth  
from itsdangerous import SignatureExpired, BadSignature
from flask_mailman import EmailMessage 
from core import admin_manager

# ✅ Initialize Admin Blueprint (Handles all admin-related actions)
from flask import Blueprint

admin_bp = Blueprint('admin', __name__,url_prefix='/admin',template_folder='templates' ) # ✅ Explicitly set template folder



@admin_manager.user_loader
def load_admin(user_id):
    """Loads an admin user from the database using Flask-Login."""
    print(f"🔹 Loading Admin User: {user_id}")

    # Query using mnc_user_id instead of default id
    user = MncUser.query.filter_by(mnc_user_id=int(user_id)).first()  
    
    print(f"🔹 User: {user}" )
    print(f"🔹 is User admin? ?: {user.is_admin}" )


    if user and user.is_admin:
        print(f"✅ Admin User Loaded: {user.mncfname} {user.mnclname}")
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



# ✅ Admin Dashboard
@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard: View municipal officials."""
    print(f"🚀 Reached admin_dashboard route! User: {current_user}")

    if not current_user.is_authenticated:
        print("❌ User is NOT authenticated. Redirecting to login.")
        return redirect(url_for('adminauth.admin_login'))

    if not isinstance(current_user, MncUser):
        print("❌ Current user is NOT an instance of MncUser.")
        return redirect(url_for('adminauth.admin_login'))

    if not current_user.is_admin:
        print("❌ Current user is NOT an admin.")
        return redirect(url_for('adminauth.admin_login'))

    admin_municipality = current_user.municipalid

    if not admin_municipality:
        flash("No admin-municipality assignment data found.", "error")
        return redirect(url_for('admin.admin_dashboard'))

    # ✅ Fetch all officials in the admin's municipality
    officials = (
        db.session.query(
            MncUser.mnc_user_id,
            MncUser.mncfname,
            MncUser.mnclname,
            MncUser.mncemail,
            MncUser.mnctitle,
            MncDepartment.deptname
        )
        .join(MncDepartment, MncUser.deptid == MncDepartment.deptid)
        .filter(MncUser.municipalid == admin_municipality)
        .all()
    )

    return render_template('admin_dashboard.html', officials=officials)



# ✅ Admin Pre-Register Official
@admin_bp.route('/pre_register', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_pre_register():
    """Allows an admin to pre-register a municipal official."""

    admin_municipality = current_user.municipalid

    if not admin_municipality:
        flash("Error: No admin-municipality assignment data found.", "error")
        return redirect(url_for('admin.admin_dashboard'))

    # ✅ Fetch departments linked to admin's municipality
    departments = MncDepartment.query.filter_by(municipalid=admin_municipality).all()

    if request.method == 'POST':
        email = request.form.get('email')
        fname = request.form.get('fname')
        lname = request.form.get('lname')
        deptid = request.form.get('dept_id')
        job_title = request.form.get('job_title')
        contact = request.form.get('contact')

        # ✅ Validate department selection
        selected_department = MncDepartment.query.filter_by(deptid=deptid, municipalid=admin_municipality).first()
        if not selected_department:
            flash("Invalid department selection.", "error")
            return redirect(url_for('admin.admin_pre_register'))

        # ✅ Check if user already exists
        if MncUser.query.filter_by(mncemail=email).first():
            flash('User with this email already exists.', 'error')
            return redirect(url_for('admin.admin_pre_register'))

        # ✅ Create new user with default password
        temp_password = "TempPass123"
        new_user = MncUser(
            mncfname=fname,
            mnclname=lname,
            mncemail=email,
            municipalid=admin_municipality,
            deptid=deptid,
            mnctitle=job_title,
            mnccontact=contact,
            password_hash=temp_password,  # Placeholder for password hashing function
            is_verified=False,
            is_sso_only=False,
            is_official=True,
            is_admin=False,
            force_password_reset=True
        )

        db.session.add(new_user)
        db.session.commit()

        # ✅ Send registration email
        token = current_app.serializer.dumps(email, salt='email-confirm')
        confirm_url = url_for('admin.admin_confirm_email', token=token, _external=True)

        msg =EmailMessage(
            subject="Confirm Your Email!",
            body=f"Click the link to confirm your email: {confirm_url}",
            from_email=current_app.config['MAIL_DEFAULT_SENDER'],
            to=[email]
        )

        msg.send()  # Send the email

        print(f"📧 Email sent to {email} with confirmation link: {confirm_url}")
        flash(f"Pre-registration successful. Email sent to {email}.", "success")
        return redirect(url_for('admin.admin_dashboard'))

    return render_template('admin_pre_register.html', municipal_id=admin_municipality, departments=departments)


# ✅ Admin Email Confirmation
@admin_bp.route('/confirm_email/<token>')
def admin_confirm_email(token):
    """Confirm email after pre-registration."""
    try:
        email = current_app.serializer.loads(token, salt='email-confirm', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('The confirmation link is invalid or has expired.', 'error')
        return redirect(url_for('mncauth.official_login'))

    user = MncUser.query.filter_by(mncemail=email).first()
    
    if user:
        user.is_verified = True
        db.session.commit()

        flash('Account verified! Please log in.', 'success')

        # ✅ Redirect based on user type
        if user.is_sso_only:  
            return redirect(url_for('mncauth.official_login'))  # Redirect SSO users

       # return redirect(url_for('mncauth.official_reset_password', token=token))  # Redirect normal users to set password

    flash('No user found. Please contact support.', 'error')
    return redirect(url_for('mncauth.official_login'))

