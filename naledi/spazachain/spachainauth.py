import re
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from core.naledimodels import UserProfile, SpazaOwner, StoreDetails, RegistrationForm, RegistrationProgress, Lesee, FoodItems,HealthCompliance,Document, UserProfileForm, IdentityVerification, MunicipalCompliance
from datetime import datetime
from core import oauth
from core import db, os
from google.cloud import storage
from core.utils import allowed_file, upload_to_gcs
#from config import ALLOWED_EXTENSIONS as allowed_extensions
from core.utils import is_valid_cellno, allowed_file, upload_to_gcs   
from flask import jsonify, g, json
from wtforms.validators import Email




#spachainauth = Blueprint('spachainauth', __name__)
spachainauth = Blueprint('spachainauth', __name__, url_prefix='/spachainauth',template_folder='templates', static_folder='static')

#google = oauth.google

google = oauth.create_client('google')  # create the google oauth client
login_manager = LoginManager()  # Create a login manager instance

@login_manager.user_loader
def load_user(user_id):
    user = UserProfile.query.get(user_id)
    if user:
        print(f"User loaded: {user.username}")
        return user

    print(f"user not not exist /  not found: {user_id}")    
    return None

#define the context processor for spachainauth. This calculatea all the progres data and makes it available to all templates
@spachainauth.context_processor
def inject_progress():
    if hasattr(g, 'user_id'):
        progress = get_registration_progress(g.user_id)
        return dict(progress=progress)
    return dict(progress=None)

# Define a before request hook to set the user id in the g object ( Flask's glaobalm context)

@spachainauth.before_request
def before_request():
   if current_user.is_authenticated:
       g.user_id = current_user.user_id
   else:    
       g.user_id = None
        

# define the function to get the registration status

#reg_form = RegistrationForm.query.filter_by(owner_id=spaza_owner.owner_id).first()

def get_registration_progress(user_profile_id):
    progress = {
        "profile_complete": "not-started",
        "registration_complete": "not-started",
        "store_details_complete": "not-started",
        "documents_uploaded": "not-started",
    }

    # ✅ Check profile existence
    user_profile = UserProfile.query.filter_by(user_profile_id=user_profile_id).first()
    if user_profile:
        progress["profile_complete"] = "completed"

    # ✅ Registration form (linked to user_profile_id now)
    reg_form = RegistrationForm.query.filter_by(user_id=user_profile_id).first()
    if reg_form:

        if reg_form.status == "submitted":
            progress["registration_complete"] = "started"
        elif reg_form.status == "registered":
            progress["registration_complete"] = "completed"
        # if reg_form.personal_details_complete or reg_form.business_type:
        #     progress["registration_complete"] = "started"
        # if (
        #     reg_form.personal_details_complete and 
        #     reg_form.address_details_complete and 
        #     reg_form.business_type
        # ):
        #     progress["registration_complete"] = "completed"

    # ✅ Store details — must resolve via SpazaOwner first
    spaza_owner = SpazaOwner.query.filter_by(user_profile_id=user_profile_id).first()
    if spaza_owner:
        store = StoreDetails.query.filter_by(owner_id=spaza_owner.owner_id).first()
        if store:
            if store.reg_status == "registered":
                progress["store_details_complete"] = "completed"
            elif store.reg_status in ("submitted", "draft"):
                progress["store_details_complete"] = "started"

    # ✅ Documents uploaded by user_profile_id
    documents = Document.query.filter_by(uploaded_by_user_id=user_profile_id).all()
    if documents:
        approved_docs = any(doc.reviewed_status == "approved" for doc in documents)
        submitted_docs = any(doc.submitted_status == "submitted" and doc.reviewed_status == "pending" for doc in documents)

        if approved_docs:
            progress["documents_uploaded"] = "completed"
        elif submitted_docs:
            progress["documents_uploaded"] = "started"

    return progress



# For users with a user profile , they can now register their spaza shop
# registration form for the main owner with a user profile  - excludes the spaza shop detaiils and the leasee details

@spachainauth.route('/register', methods=['GET', 'POST'])
@login_required
def spachainauth_register():
    user_profile = current_user if isinstance(current_user, UserProfile) else None

    if not user_profile:
        flash('User profile not loaded correctly. Please complete your profile first.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))

    user_id = user_profile.user_profile_id
    email = user_profile.email
    cellno = user_profile.cellno

    print(f"🔹 UserProfile loaded: ID={user_id}, Email={email}, Cell={cellno}")

    # ✅ Redirect early if already registered
    existing_registration = RegistrationForm.query.filter_by(user_id=user_id).first()
    if existing_registration:
        flash('You are already registered. Redirecting to your profile...', category='info')
        return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=user_id))

    if request.method == 'POST':
        business_type = request.form.get('businessType')
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        dob = request.form.get('dob')
        gender = request.form.get('gender')
        citizenship = request.form.get('citizenship')
        id_number = request.form.get('saId')
        street_address = request.form.get('streetAddress')
        address2 = request.form.get('address2')
        city = request.form.get('city')
        province = request.form.get('province')
        postal_code = request.form.get('postcode')
        district_mnc = request.form.get('municipality')

        required_fields = {
            "Business Type": business_type, "First Name": first_name,
            "Last Name": last_name, "Date of Birth": dob, "Gender": gender,
            "ID Number": id_number if citizenship == 'South Africa' else 'N/A',
            "Street Address": street_address, "City": city,
            "Postal Code": postal_code, "Province": province, "District": district_mnc
        }

        print(f"📝 Collected Registration Data: {required_fields}")

        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            flash(f"Please provide values for: {', '.join(missing_fields)}", category='error')
            return redirect(url_for('spachainauth.spachainauth_register'))

        try:
        # ✅ 1. Create the RegistrationForm first
            registration = RegistrationForm(
                user_id=user_id,
                business_type=business_type.strip(),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                dob=dob.strip(),
                gender=gender.strip(),
                citizenship=citizenship.strip(),
                id_number=id_number.strip() if id_number else None,
                street_address=street_address.strip(),
                address2=address2.strip(),
                city=city.strip(),
                postal_code=postal_code.strip(),
                province=province.strip(),
                district_mnc=district_mnc.strip(),
                status="submitted"
                )
            db.session.add(registration)
            db.session.flush()  # 👈 ensures reg_id is available before commit

            # ✅ 2. Now use registration.reg_id to create SpazaOwner
            existing_owner = SpazaOwner.query.filter_by(user_profile_id=user_id).first()
            if not existing_owner:
                new_owner = SpazaOwner(
                    name=first_name.strip(),
                    surname=last_name.strip(),
                    email=email,
                    address=street_address.strip(),
                    said=id_number.strip() if id_number else 'N/A',
                    user_profile_id=user_id,
                    reg_id=registration.reg_id  # ✅ assign the FK properly
                )
                db.session.add(new_owner)

            db.session.commit()
            flash('Registration successful!', category='success')
            #return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=user_id))
            return redirect(url_for('spachainauth.spachainauth_home', user_id=user_id))

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error during registration: {str(e)}", category='error')
            print(f"❌ Error: {e}")
            return redirect(url_for('spachainauth.spachainauth_register'))

    return render_template('spachainauth_register.html', title='Spaza Owner Registration')

# route for home and profile routes for registered users

"""@spachainauth.route('/home', methods=['GET', 'POST'])
@login_required
def spachainauth_home():
    
    return render_template("spachainauth_home.html", user=current_user) """

# route to retun=rn the logged on user to the their dashboard
@spachainauth.route("/home")
@login_required
def spachainauth_home():
    print("Reached SpachainAuth Home")

    # Use user_profile_id for consistency
    user_id = current_user.user_profile_id
    spaza_owner = SpazaOwner.query.filter_by(user_profile_id=user_id).first()

    store = None
    progress = get_registration_progress(user_id)  # ✅ Pass correct ID
    verifications = generate_verification_status(user_id)
    compliance_status = generate_compliance_status(user_id)

    if spaza_owner:
        store = StoreDetails.query.filter_by(owner_id=spaza_owner.owner_id).first()

        if store:
            if store.reg_status in ['registered', 'draft']:
                print("Store is registered or draft")
                current_user.has_registered_store = True
                if store.reg_status == 'registered':
                    flash('You have already registered your store!', 'success')
                else:
                    flash('Your store is in draft status. Please complete the registration.', 'info')
            else:
                current_user.has_registered_store = False
                flash('Your store registration is pending or unknown.', 'warning')
        else:
            current_user.has_registered_store = False
            flash('No store registered yet.', 'warning')
    else:
        current_user.has_registered_store = False

    return render_template("spachainauth_home.html", user=current_user, store=store, progress=progress,verifications=verifications, compliance_status=compliance_status)

# owner details for the spaza shop owner
#@spachainauth.route('/owner-details/<int:user_id>', methods=['GET', 'POST'])
@spachainauth.route('/owner-details', methods=['GET', 'POST'])
@login_required
def spachainauth_owner_details():
    user = current_user  # ✅ Corrected from `current_user.use`

    if not user:
        flash('No user profile exists. Ensure your registration is completed.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))

    registration = RegistrationForm.query.filter_by(user_id=user.user_profile_id).first()
    if not registration:
        flash('No registration details found. Please complete the registration form first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_register'))

    # Check if owner already exists
    owner = SpazaOwner.query.filter_by(user_profile_id=user.user_profile_id).first()

    if request.method == 'POST':
        # Form inputs
        name = request.form.get('name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        address = request.form.get('address')
        said = request.form.get('said')

        if owner:
            flash('Owner details already exist.', category='error')
            return redirect(url_for('spachainauth.spachainauth_owner_details'))

        # ✅ Create new owner
        new_owner = SpazaOwner(
            user_profile_id=user.user_profile_id,
            name=name,
            surname=surname,
            email=email,
            address=address,
            said=said
        )
        db.session.add(new_owner)
        db.session.commit()
        flash('Owner details saved successfully!', category='success')
        return redirect(url_for('spachainauth.spachainauth_owner_details'))

    return render_template("spachainauth_owner_details.html", user=user, owner=owner, registration=registration)


# define a route to make spaza owner available to all templates

@spachainauth.context_processor
def inject_spaza_owner():
    if current_user.is_authenticated:
        owner = SpazaOwner.query.filter_by(user_profile_id=current_user.user_profile_id).first()

        return dict(spaza_owner=owner)
    return dict(spaza_owner=None)  



# route for the owner to be able to regisyte the store details
@spachainauth.route('/store', methods=['GET', 'POST'])
@login_required
def spachainauth_store():
    user_id = current_user.user_profile_id
    user_profile = UserProfile.query.filter_by(user_profile_id=user_id).first()

    if not user_profile:
        flash('No user profile found. Please complete your profile first.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))

    spaza_owner = SpazaOwner.query.filter_by(user_profile_id=user_id).first()

    if not spaza_owner:
        flash('You need to complete your registration first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_register'))

    existing_stores = StoreDetails.query.filter_by(owner_id=spaza_owner.owner_id).all()

    if request.method == 'POST':
        # Normalize inputs
        storetype = request.form.get('storetype', '').strip()
        store_name = request.form.get('store_name', '').strip()
        storevolume = request.form.get('storevolume', '').strip()
        cicpno = request.form.get('cicpno', '').strip()
        sarsno = request.form.get('sarsno', '').strip()
        permit_id = request.form.get('permitid', '').strip()
        zonecertno = request.form.get('zonecertno', '').strip()
        ownershipstatus = request.form.get('ownershipstatus', '').strip().lower()
        storeaddress = request.form.get('storeaddress', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        province = request.form.get('province', '').strip()
        district_mnc = request.form.get('municipality', '').strip()

        # Lessee fields
        leseefname = request.form.get('leseefname', '').strip()
        leseelname = request.form.get('leseelname', '').strip()
        lesee_id_no = request.form.get('lesee_id_no', '').strip()

        # Validate required store fields
        required_fields = {
            "Store Type": storetype, "Store Name": store_name, "Store Volume": storevolume,
            "CIPC Number": cicpno, "SARS Number": sarsno, "Permit ID": permit_id,
            "Zoning Certification": zonecertno, "Ownership Status": ownershipstatus,
            "Store Address": storeaddress, "City": city, "Postal Code": postal_code,
            "Province": province, "District": district_mnc
        }
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            flash(f"Store data missing: {', '.join(missing_fields)}", category='error')
            return redirect(url_for('spachainauth.spachainauth_store'))

        # ✅ If rented, lessee fields must be present
        if ownershipstatus.lower() == "rented":
            required_lessee_fields = {
                "Lessee First Name": leseefname,
                "Lessee Last Name": leseelname,
                "Lessee ID": lesee_id_no
            }
            #missing_lessee_fields = [field for field, value in required_lessee_fields.items() if not value]
            missing_lessee_fields = [label for label, val in required_lessee_fields.items() if not val]
            if missing_lessee_fields:
                flash(f"Please provide the Store Renter's details: {', '.join(missing_lessee_fields)}", category='error')
                return redirect(url_for('spachainauth.spachainauth_store'))

        try:
            # ✅ Create Store record
            store = StoreDetails(
                storetype=storetype,
                store_name=store_name,
                storevolume=storevolume,
                cicpno=cicpno,
                sarsno=sarsno,
                permit_id=permit_id,
                zonecertno=zonecertno,
                compstatus="submitted status",
                ownershipstatus=ownershipstatus,
                storeaddress=storeaddress,
                city=city,
                postal_code=postal_code,
                province=province,
                district_mnc=district_mnc,
                owner_id=spaza_owner.owner_id
            )
            db.session.add(store)
            db.session.flush()  # ✅ So we can get store.store_id before commit

           
            # ✅ Only add Lessee if rented
            if ownershipstatus.lower() == "rented":
                new_lesee = Lesee(
                    leseefname=leseefname,
                    leseelname=leseelname,
                    lesee_id_no=lesee_id_no,
                    leseeemail="draft@example.com",
                    leseeaddress="draft address",
                    leseestoreid=store.store_id,
                    owner_id=spaza_owner.owner_id
                )
                db.session.add(new_lesee)

            db.session.commit()
            flash("Store (and lessee if applicable) saved successfully!", category="success")
            return redirect(url_for('spachainauth.spachainauth_home'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error saving store or lessee: {str(e)}", category="error")
            return redirect(url_for('spachainauth.spachainauth_store'))

    # GET request   
    return render_template(
        'spachainauth_store.html',
        title='Spaza Owner Store Details',
        user=current_user,
        existing_stores=existing_stores
    )



#Define to help determine if there are exsiting store for a registered owner
@spachainauth.route('/store_manage', methods=['GET'])
@login_required
def spachainauth_store_manage():
    user_id = current_user.user_profile_id
    spaza_owner = SpazaOwner.query.filter_by(owner_id=user_id).first()

    existing_stores = []
    if spaza_owner:
        existing_stores = StoreDetails.query.filter_by(owner_id=spaza_owner.owner_id).all()

    return render_template(
        'spachainauth_store_manage.html',
        user=current_user,
        existing_stores=existing_stores
    )


# Route to capture food list items for the store 
# the route to handle food items selected by the store owner
@spachainauth.route('/food_items', methods=['GET', 'POST'])
@login_required
def spachainauth_food_items():
    if request.method == 'POST':
        # Capture selected food items
        selected_items = request.form.getlist('food_items')
        other_item = request.form.get('food_other')

        # Append "Other" item if specified
        if 'Other' in selected_items and other_item:
            selected_items.append(other_item)

        # Save food items to the database
        food_entry = FoodItems(
            user_id=current_user.user_profile_id,
            selected_items=selected_items
        )
        try:
            db.session.add(food_entry)
            db.session.commit()
            flash('Food items saved successfully!', category='success')
            return redirect(url_for('naledi.naledi_home',user=current_user))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while saving your food items.', category='error')
            print(f'Error: {e}')

    return render_template('spachainauth_food_items.html',user=current_user)

# The route for health compliance for the store owner
@spachainauth.route('/health_self_check', methods=['GET', 'POST'])
@login_required
def spachainauth_health_self_check():
    user_id = current_user.user_profile_id

    print(f"Health Compliance User ID: {user_id}")

    owner = SpazaOwner.query.filter_by(owner_id=user_id).first()
    if not owner:
        flash('Owner details not found. Please complete owner details first.', category='error')
        return redirect(url_for('spachainauth.owner_details', user_id=current_user.user_profile_id))

    print(f"health Owner ID: {owner.user_id}")
    if request.method == 'POST':
        # Capture form data and structure it with a status field
        sanitary_facilities = {
            "status": "compliant" if request.form.getlist('sanitary_facilities') else "pending",
            "details": request.form.getlist('sanitary_facilities')
        }
        cleaning_facilities = {
            "status": "compliant" if request.form.getlist('cleaning_facilities') else "pending",
            "details": request.form.getlist('cleaning_facilities')
        }
        handwashing_stations = {
            "status": "compliant" if request.form.getlist('handwashing_stations') else "pending",
            "details": request.form.getlist('handwashing_stations')
        }
        waste_disposal = {
            "status": "compliant" if request.form.getlist('waste_disposal') else "pending",
            "details": request.form.getlist('waste_disposal')
        }
        food_handling = {
            "status": "compliant" if request.form.getlist('food_handling') else "pending",
            "details": request.form.getlist('food_handling')
        }
        food_storage = {
            "status": "compliant" if request.form.getlist('food_storage') else "pending",
            "details": request.form.getlist('food_storage')
        }
        food_preparation = {
            "status": "compliant" if request.form.getlist('food_preparation') else "pending",
            "details": request.form.getlist('food_preparation')
        }
        food_prep_tools = {
            "status": "compliant" if request.form.getlist('food_prep_tools') else "pending",
            "details": request.form.getlist('food_prep_tools')
        }
        employees = {
            "men": request.form.get('men-employed'),
            "women": request.form.get('women-employed'),
            "total": request.form.get('total-employed')
        }

        fields_completed = {
            "sanitary_facilities": sanitary_facilities,
            "cleaning_facilities": cleaning_facilities,
            "handwashing_stations": handwashing_stations,
            "waste_disposal": waste_disposal,
            "food_handling": food_handling,
            "food_storage": food_storage,
            "food_preparation": food_preparation,
            "food_prep_tools": food_prep_tools,
            "employees": employees
        }

        print(f"Health Compliance data: {fields_completed}")

        # Create a new record in the HealthCompliance table
        health_compliance = HealthCompliance(
            user_id=current_user.user_id,
            sanitary_facilities=sanitary_facilities,
            cleaning_facilities=cleaning_facilities,
            handwashing_stations=handwashing_stations,
            waste_disposal=waste_disposal,
            food_handling=food_handling,
            food_storage=food_storage,
            food_preparation=food_preparation,
            food_prep_tools=food_prep_tools,
            employees=employees
        )

        try:
            db.session.add(health_compliance)
            db.session.commit()
            flash('Health compliance data saved successfully!', category='success')
            return redirect(url_for('naledi.naledi_home', user=current_user))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while saving the data.', category='error')
            print(f'Error: {e}')
            return redirect(url_for('spachainauth.spachainauth_health_self_check', owner=owner, user=current_user))

    return render_template('spachainauth_health_self_check.html', user=current_user)





@spachainauth.route('/registration_progress', methods=['GET', 'POST'])
@login_required
def spachainauth_registration_progress():
    user_id = current_user.user_profile_id

    # Check if the user has a profile
    # user_profile = UserProfile.query.get(user_id)
    # if not user_profile:
    #     flash('No user profile found. Please complete your profile first.', category='error')
    #     return redirect(url_for('naledi.naledi_sign_up'))

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


# Route to display  user profile for a registered user 
@spachainauth.route('/userprofile', methods=['GET', 'POST'])
@login_required
def spachainauth_userprofile():
    user_id = current_user.user_profile_id
    user_profile = UserProfile.query.get(user_id)

    form = UserProfileForm(obj=user_profile)

    if form.validate_on_submit():
        form.populate_obj(user_profile)
        db.session.commit()
        flash("Profile updated!", "success")

    return render_template("spachainauth_userprofile.html", user=current_user, form=form)

@spachainauth.route('/spusers', methods=['GET', 'POST'])
@login_required
def spachainauth_spusers():
    #return render_template("services.html", user=current_user)
    return render_template("spusers.html", user=current_user)

# the route to update user profule imformation : address , secondary phone,primary cell phone for social login users  
@spachainauth.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
   
    owner = SpazaOwner.query.filter_by(user_profile_id=current_user.user_profile_id).first()

    if request.method == 'POST':
        name = request.form.get('name')
        cellno = request.form.get('cellno')
        address = request.form.get('address')

        if not is_valid_cellno(cellno):
            flash('Invalid phone number.', category='error')
            return redirect(url_for('spachainauth.update_profile'))

        # Update user profile
        current_user.username = name
        current_user.cellno = cellno

        # Update or create owner profile
       # owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()
        if not owner:
            owner = SpazaOwner(user_profile_id=current_user.user_profile_id)
            db.session.add(owner)
        owner.address = address

        db.session.commit()
        flash('Profile updated successfully!', category='success')
        return redirect(url_for('spachainauth.spachainauth_userprofile'))

    return render_template('spachainauth_update_profile.html', user=current_user)


# done for showing customer compliance tracking progress
@spachainauth.route('/spusers', methods=['GET', 'POST'])
@login_required
def spusers():
    # Check if the user has a profile or services to display
    user_profile = UserProfile.query.get(current_user.user_profile_id)
    
    if not user_profile:
        # If no profile exists, redirect to registration or an appropriate page
        flash("Please complete your profile to access services.", category="warning")
        return redirect(url_for('spachainauth.sign_up'))

    # If the user has a profile, display their services or profile
    return render_template("sign_up.html", user=user_profile)


# to be done to include services to subscribe to like compliance tracking
@spachainauth.route('/services')
def spachainauth_services():
    #return render_template("services.html", user=current_user)
    return render_template("spachainauth_services.html", user=current_user)



@spachainauth.route('/upload_docs', methods=['GET', 'POST'])
@login_required
def spachainauth_upload_docs():
    """Allow users to upload some documents now and return later."""

    document_types = {
        'id_passport_visa': 'ID/Passport/Visa [Required for all owners]',
        'proof_of_address': 'Proof of Address [ Utility Bill or Letter from Municipality]',
        'permit': 'Permit [Municipal Trading Permit]',
        'health_certificate': 'Certificate of Acceptability [ Issued by the Environmental Health Department of the municipality ]',
        'zoning_certificate': 'Zoning certificate or Special Consent Approval[To be obtaioned from the Municipality]',
        'building_plans': 'Building plans [Required for any building alterations or new buildings]',
        'title_deed_or_Lease agreement': 'Title deed or Lease Agreement',
        'banking_confirmation': 'Banking confirmation [ Proof of your South African Bank Account]',
        'cipc': 'CIPC [ Company Registration Certificate]',
        'sars': 'SARS Tax Clearance [ This can be obtained from SARS to show you dont have outstanding taxes]',
        'affidavit': 'Affidavit [Proof that you are not engaged in illegal trading of goods]'   
    }

    # Fetch already uploaded documents
    existing_docs = {doc.document_type: doc for doc in Document.query.filter_by(uploaded_by_user_id=current_user.user_profile_id).all()}

    if request.method == 'POST':
        for field_name, document_type in document_types.items():
            file = request.files.get(field_name)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                destination_blob_name = f'{current_user.user_id}/{document_type}_{filename}'
                file_url = upload_to_gcs(file, destination_blob_name)

                if document_type in existing_docs:
                    # ✅ Update existing document
                    existing_docs[document_type].file_url = file_url
                    existing_docs[document_type].filename = filename
                else:
                    # ✅ Add new document
                    new_document = Document(
                        uploaded_by_user_id=current_user.user_profile_id,
                        document_type=document_type,
                        file_url=file_url,
                        file_name=filename,
                        submitted_status ="submitted", # mark as submitted
                        reviewed_status ="pending", # Default
                        approved_status="pending"   # Default
                    )
                    db.session.add(new_document)

        db.session.commit()
        flash('Documents uploaded successfully!', 'success')
        return redirect(url_for('spachainauth.spachainauth_upload_docs'))
        #return render_template('spachainauth_upload_docs.html', existing_docs=existing_docs)

    # ✅ Identify missing documents
    missing_docs = {key: value for key, value in document_types.items() if value not in existing_docs}

    return render_template('spachainauth_upload_docs.html', existing_docs=existing_docs, missing_docs=missing_docs)


@spachainauth.route('/view_docs', methods=['GET', 'POST'])
@login_required
def spachainauth_view_docs():
    """Allows users to view and update uploaded documents."""
    
    document_types = {
        'id_passport_visa': 'ID/Passport/Visa [Required for all owners]',
        'proof_of_address': 'Proof of Address [ Utility Bill or Letter from Municipality]',
        'permit': 'Permit [Municipal Trading Permit]',
        'health_certificate': 'Certificate of Acceptability [ Issued by the Environmental Health Department of the municipality ]',
        'zoning_certificate': 'Zoning certificate or Special Consent Approval[To be obtaioned from the Municipality]',
        'building_plans': 'Building plans [Required for any building alterations or new buildings]',
        'title_deed_or_Lease agreement': 'Title deed or Lease Agreement',
        'banking_confirmation': 'Banking confirmation [ Proof of your South African Bank Account]',
        'cipc': 'CIPC [ Company Registration Certificate]',
        'sars': 'SARS Tax Clearance [ This can be obtained from SARS to show you dont have outstanding taxes]',
        'affidavit': 'Affidavit [Proof that you are not engaged in illegal trading of goods]'   
    }

    # Fetch existing documents
    existing_docs = {doc.document_type: doc for doc in Document.query.filter_by(uploaded_by_user_id=current_user.user_profile_id).all()}
    
    if request.method == 'POST':
        for field_name, document_type in document_types.items():
            file = request.files.get(field_name)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                destination_blob_name = f'{current_user.user_profile_id}/{document_type}_{filename}'
                file_url = upload_to_gcs(file, destination_blob_name)

                if document_type in existing_docs:
                    # ✅ Update existing document
                    existing_docs[document_type].file_url = file_url
                    existing_docs[document_type].filename = filename
                else:
                    # ✅ Add new document (shouldn't happen here, but as a fallback)
                    new_document = Document(
                       uploaded_by_user_id=current_user.user_profile_id,
                        document_type=document_type,
                        file_url=file_url,
                        file_name=filename
                    )
                    db.session.add(new_document)

        db.session.commit()
        return redirect(url_for('spachainauth.spachainauth_view_docs'))  # Refresh page after update

    return render_template('spachainauth_view_docs.html', existing_docs=existing_docs)



@spachainauth.route('/doc_verify_status', methods=['GET'])
@login_required
def doc_verify_status():
    """Fetches submitted and missing documents for the user."""
    
    document_types = {
        'id_passport_visa': 'ID/Passport/Visa [Required for all owners]',
        'proof_of_address': 'Proof of Address [ Utility Bill or Letter from Municipality]',
        'permit': 'Permit [Municipal Trading Permit]',
        'health_certificate': 'Certificate of Acceptability [ Issued by the Environmental Health Department of the municipality ]',
        'zoning_certificate': 'Zoning certificate or Special Consent Approval [To be obtained from the Municipality]',
        'building_plans': 'Building plans [Required for any building alterations or new buildings]',
        'title_deed_or_lease_agreement': 'Title deed or Lease Agreement',
        'banking_confirmation': 'Banking confirmation [ Proof of your South African Bank Account]',
        'cipc': 'CIPC [ Company Registration Certificate]',
        'sars': 'SARS Tax Clearance [ This can be obtained from SARS to show you don’t have outstanding taxes]',
        'affidavit': 'Affidavit [Proof that you are not engaged in illegal trading of goods]'   
    }

    # Fetch existing documents for the current user
    existing_docs = {doc.document_type for doc in Document.query.filter_by(uploaded_by_user_id=current_user.user_profile_id).all()}

    # Determine missing documents
    submitted_docs = {key: value for key, value in document_types.items() if key in existing_docs}
    missing_docs = {key: value for key, value in document_types.items() if key not in existing_docs}

    return jsonify({
        "submitted_documents": submitted_docs,
        "missing_documents": missing_docs
    })


# route to display the documents uploaded by the store owner
@spachainauth.route('/view_docs', methods=['GET'])
@login_required
def spachainauth_ver_docs():
    """Render the document view page with submitted and missing documents."""
    
    progress = doc_verify_status()  # Call the function to get documents

    return render_template('spachainauth_ver_docs.html', 
                           submitted_docs=progress.json["submitted_documents"], 
                           missing_docs=progress.json["missing_documents"])



# function to generate a dashboard for the end user with dynamic data
def generate_doc_status_dashboard(user_id):
    """
    Generate a dashboard for the end user with dynamic data.

    Args:
        user_id (int): The ID of the current user.

    Returns:
        dict: A dictionary containing document status and registration progress.
    """
    # Fetch documents from the database
    documents = Document.query.filter_by(uploaded_by_user_id=user_id).all()

    # Format documents for the dashboard
    formatted_documents = []
    for doc in documents:
        formatted_documents.append({
            "name": doc.document_type,  # Use document_type as the name
            "submitted": doc.submitted_status,
            "reviewed": doc.reviewed_status,
            "approved": doc.approved_status,
        })

    # Fetch registration progress
    progress = get_registration_progress(user_id)

    return {
        "submitted_documents": formatted_documents,
        "registration_progress": progress,
    }

# define a function to generate a dashboard card for the health and safety complianee for the 
def extract_status(json_field, field_name):
    """Ensure JSON is properly parsed and extract 'status'."""
    print(f"🛠 Extracting {field_name}: Raw Data -> {json_field}")  # Debugging Output

    if not json_field or json_field == []:
        print(f"⚠️ Warning: {field_name} is empty. Defaulting to 'pending'.")
        return "pending"

    try:
        if isinstance(json_field, str):
            print(f"🔄 Converting string to JSON for {field_name} -> {json_field}")  
            json_field = json.loads(json_field.replace("'", "\""))  # Convert JSON string if needed

        if isinstance(json_field, dict):
            print(f"✅ Parsed {field_name}: {json_field}")  # Debugging Output

            if field_name == "Employees":
                return "compliant" if json_field.get("total") else "pending"

            if "status" in json_field:
                return json_field["status"]
            else:
                print(f"⚠️ No 'status' key found in {field_name} -> {json_field}")
                return "pending"
    except Exception as e:
        print(f"❌ Error processing {field_name}: {e} | Data: {json_field}")  
        return "pending"

    return "pending"



def get_health_compliance_data(user_id):
    """Fetch and format health compliance data for the dashboard."""
    health_compliance = HealthCompliance.query.filter_by(user_id=user_id).first()

    if not health_compliance:
        return {"compliant": [], "missing": []}

    compliance_items = {
        "Sanitary Facilities": health_compliance.sanitary_fac,
        "Cleaning Facilities": health_compliance.cleaning_fac,
        "Handwashing Stations": health_compliance.hand_wash_fac,
        "Waste Disposal": health_compliance.waste_disp,
        "Food Handling": health_compliance.food_hand_fac,
        "Food Storage": health_compliance.food_store_fac,
        "Food Preparation": health_compliance.foodprep_proc,
        "Food Prep Tools": health_compliance.foodprep_tool,
        "Employees": health_compliance.employees
    }

    print(f"📌 Raw Database Data: {compliance_items}")  # Debugging - Print Raw Data

    compliant = []
    missing = []

    for name, field in compliance_items.items():
        print(f"📌 Processing {name}: {field}")  # Debugging - Check Raw Data from DB
        status = extract_status(field, name)  # Pass field name for debugging

        if status == "compliant":
            compliant.append({"name": name, "status": "compliant"})
        else:
            missing.append({"name": name, "status": "pending"})

    result = {"compliant": compliant, "missing": missing}

    print(f"✅ FINAL Compliance Data: {result}")  # Debugging output
    return result

#function to provide simplifoed view for the end uer to see their verification status relating to :
# 1. Indentity verification
# 2. Tax clearance
# 3. Company registration
# 4. Police clearance
# 5. Lease or title deed 
   

# function to generate a dashboard for the end user with dynamic data. This function will enable the user to see their status in a dashboard format
# and will be used to display the status of the documents uploaded by the user
def generate_verification_status(user_id):
    """
    Generate a dashboard for the end user with dynamic data.

    Args:
        user_id (int): The ID of the current user.

    Returns:
        dict: A dictionary containing verification statuses.
    """
    # Fetch records where FK matches the spaza_owner_id
    identity_verifications = IdentityVerification.query.filter_by(spaza_owner_id=user_id).all()

    verifications = []
    for ver in identity_verifications:
        verifications.append({
            "Owner Identity Verification": ver.owner_verified_id,
            "Lesee Identity Verification": ver.lesee_verified_id,
            "Tax Clearance": ver.tax_clearance,
            "Company Registration": ver.company_registration,
            "Police Clearance": ver.police_clearance,
        })

    return {
        "Verification Status": verifications
    }


# function to provide a simplified view of the municipal compliance status for the end user. This function reflecs status as updated by muncipal officers
def generate_compliance_status(user_id):
    """
    Generate a dashboard for the end user with compliance info.

    Args:
        user_id (int): The ID of the current user.

    Returns:
        dict: A dictionary containing compliance statuses.
    """
    compliance_records = MunicipalCompliance.query.filter_by(spaza_owner_id=user_id).all()

    compliance_status = []
    for comp in compliance_records:
        compliance_status.append({
            "Certificate Of Acceptability": comp.verified_coa,
            "Fire Inspection": comp.verified_fire_insp,
            "Zoning Certificate": comp.verified_zoning_cert,
            "Electrical Certificate": comp.verified_elec_cert,
            "Building Certificate": comp.verified_building_cert,
        })

    return {
        "Compliance Status": compliance_status
    }




















# Route to displace compliance status  for the store owner. The compliance excerciser is performed by the health inspector
# and the store owner is notified of the compliance status
# Route to display health compliance actions for the store owner
@spachainauth.route('/health_compliance')
@login_required
def health_compliance():
    print("reached health compliance")
    # Check if the user has a profile or services to display
    user_profile = UserProfile.query.get(current_user.user_profile_id)
    if not user_profile:
        # If no profile exists, redirect to registration or an appropriate page
        flash("Please complete your profile to access services.", category="warning")
        return redirect(url_for('spachainauth.sign_up'))
   
    compliance_data = get_health_compliance_data(current_user.user_profile_id)
    if not compliance_data:
        flash("No health compliance data found.", category="warning")
        #return redirect(url_for('spachainauth.spachainauth_health_self_check'))

    return render_template("spachainauth_health_compliance.html", user=current_user,compliance_data=compliance_data)

# function to get fire compliance data for the store owner. This will be complete later
def get_fire_compliance_data(user_id):
    """Fetch and format health compliance data for the dashboard."""
    fire_compliance = HealthCompliance.query.filter_by(user_id=user_id).first()

    if not health_compliance:
        return {"compliant": [], "missing": []}

    compliance_items = {
        "Sanitary Facilities": health_compliance.sanitary_facilities,
        "Cleaning Facilities": health_compliance.cleaning_facilities,
        "Handwashing Stations": health_compliance.handwashing_stations,
        "Waste Disposal": health_compliance.waste_disposal,
        "Food Handling": health_compliance.food_handling,
        "Food Storage": health_compliance.food_storage,
        "Food Preparation": health_compliance.food_preparation,
        "Food Prep Tools": health_compliance.food_prep_tools,
        "Employees": health_compliance.employees
    }

    print(f"📌 Raw Database Data: {compliance_items}")  # Debugging - Print Raw Data

    compliant = []
    missing = []

    for name, field in compliance_items.items():
        print(f"📌 Processing {name}: {field}")  # Debugging - Check Raw Data from DB
        status = extract_status(field, name)  # Pass field name for debugging

        if status == "compliant":
            compliant.append({"name": name, "status": "compliant"})
        else:
            missing.append({"name": name, "status": "pending"})

    result = {"compliant": compliant, "missing": missing}

    print(f"✅ FINAL Compliance Data: {result}")  # Debugging output
    return result







# Route to display  fire safety compliance actions for the store owner
@spachainauth.route('/fire_compliance', methods=['GET', 'POST'])
@login_required
def fire_compliance():
     user_profile = UserProfile.query.get(current_user.user_id)
     if not user_profile:
        # If no profile exists, redirect to registration or an appropriate page
        flash("Please complete your profile to access services.", category="warning")
        return redirect(url_for('spachainauth.sign_up'))
    
     return render_template("spachainauth_fire.html", user=current_user)

# Route to display  zoning by laws alignment for the store 
@spachainauth.route('/compliance/zoning', methods=['GET', 'POST'])
@login_required
def spachainauth_zoning():
    #return render_template("services.html", user=current_user)
    return render_template("spachainauth_zoning.html", user=current_user)

# Route to display  electrical compliance  by laws alignment for the store 
@spachainauth.route('/compliance/electrical', methods=['GET', 'POST'])
@login_required
def spachainauth_electrical():
    #return render_template("services.html", user=current_user)
    return render_template("spachainauth_electrical.html", user=current_user)

# Route to display  building plans alignment  by laws alignment for the store 
@spachainauth.route('/compliance/building', methods=['GET', 'POST'])
@login_required
def spachainauth_building():
    #return render_template("services.html", user=current_user)
    return render_template("spachainauth_building.html", user=current_user)



# dashboard route for the store and documents status, verifcation and approval
@spachainauth.route('/dashboard', methods=['GET'])
@login_required
def spachainauth_dashboard():
    """
    Render the document view page with submitted and missing documents.
    """
    # Generate dashboard data
    dashboard_data = generate_doc_status_dashboard(current_user.user_profile_id)

    # Fetch health compliance data
    compliance_data = get_health_compliance_data(current_user.user_profile_id)

    print(f"Dashboard Data: {compliance_data}")

    # Render the template with the dashboard data
    return render_template('spachainauth_dashboard.html',
                           submitted_docs=dashboard_data["submitted_documents"],
                           compliance_data=compliance_data,
                           registration_progress=dashboard_data["registration_progress"])



