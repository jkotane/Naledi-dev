from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from core import admin_manager
from core.naledimodels import MncUser

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")

@admin_manager.user_loader
def load_admin(user_id):
    """Loads official user for Flask-Login session tracking."""
    user = MncUser.query.get(int(user_id))
    if user and user.is_admin:
        return user
    return None

@admin_bp.route("/")
@login_required
def admin_landing():
    """Landing page just for admin users."""
    print(f"🔍 Landing for admin users: {current_user}")
    if not isinstance(current_user, MncUser) or not current_user.is_admin:
        flash("Unauthorized access. Please log in as an adminl.", "error")
        return redirect(url_for("adminauth.admin_login"))
    
    return render_template("admin_home.html", user=current_user)