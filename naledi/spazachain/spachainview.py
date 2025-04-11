from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import json
from core.naledimodels import UserProfile, SpazaOwner, StoreDetails, RegistrationForm, RegistrationProgress, Lesee, FoodItems,HealthCompliance


spachainview = Blueprint('spachainview', __name__)


#@spachainview.route('/', methods=['GET', 'POST'])
@spachainview.route('/', methods=['GET'])
@login_required
def home():
        
    # If the user is not authenticated
       #flash("Please log in to continue.", category="warning") """
        
        return render_template("home.html", user=current_user)
        #return render_template("reg_detail.html", user=current_user)

@spachainview.route('/login', methods=['GET'])
def login():
    return render_template("login.html", user=current_user)

@spachainview.route('/sign_up', methods=['GET'])
def sign_up():
    return render_template("sign_up.html", user=current_user)

@spachainview.route('/register')
def register():
    return render_template("register.html", user=current_user)

@spachainview.route('/register_store')
def register_store():
    return render_template("register_store.html", user=current_user)


@spachainview.route('/reg_detail')
@login_required
def reg_detail():
    # Fetch the user's registration record
    registration = RegistrationForm.query.filter_by(user_id=current_user.id).first()
    print(f"Registration object: {registration}")
    
    if not registration:
        flash('No owner registration details found.', category='warning')
        return render_template("home.html", user=current_user)  # Redirect to home or another suitable page
    
    # Render the registration details
    return render_template("reg_detail.html", user=current_user, registration=registration)



@spachainview.route('/update_registration')
def update_registration():
    registration = RegistrationForm.query.filter_by(user_id=current_user.id).first()
    if not registration:
        flash('No registration details to update.', category='warning')
    return render_template("update_registration.html", user=current_user,registration=registration)


@spachainview.route('/update_progress')
def update_progress():
    return render_template("update_progress.html", user=current_user)



@spachainview.route('/profile', methods=['GET'])
@login_required
def profile():

    # Fetch owner details
    owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()
    if not owner:
        flash('No owner details found.', category='warning')
    return render_template('profile.html', user=current_user,owner=owner)
   #return render_template('profile.html', user=current_user)

@spachainview.route('/owner-details', methods=['GET'])
@login_required
def owner_details():
    # Fetch owner details
    owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()
    if not owner:
        flash('No owner details found.', category='warning')

    return render_template('owner_details.html', user=current_user, owner=owner)
   

@spachainview.route('/spusers', methods=['GET'])
@login_required
def spusers():
    return render_template('spusers.html', user=current_user)

@spachainview.route('/about')
def about():
    return render_template("about.html", user=current_user)



