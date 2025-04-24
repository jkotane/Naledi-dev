from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from core import official_login_manager
from core.naledimodels import MncUser

official_bp = Blueprint("official_bp", __name__, url_prefix="/official")

@official_login_manager.user_loader
def load_official(user_id):
    """Loads official user for Flask-Login session tracking."""
    user = MncUser.query.get(int(user_id))
    if user and user.is_official:
        return user
    return None

@official_bp.route("/")
@login_required
def official_landing():
    """Landing page just for official users."""
    print(f"🔍 Landing for official user: {current_user}")
    if not isinstance(current_user, MncUser) or not current_user.is_official:
        flash("Unauthorized access. Please log in as an official.", "error")
        return redirect(url_for("mncauth.official_login"))
    
    #return render_template("official_landing.html", user=current_user)
    return render_template("official_home.html", user=current_user)