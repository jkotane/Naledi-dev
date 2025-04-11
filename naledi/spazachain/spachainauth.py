import re
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from core.naledimodels import UserProfile, SpazaOwner, StoreDetails, RegistrationForm, RegistrationProgress, Lesee, FoodItems,HealthCompliance,Document, UserProfileForm
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
       g.user_id = current_user.id
   else:    
       g.user_id = None
        

# define the function to get the registration status

def get_registration_progress(user_id):
    progress = {
        "profile_complete": "not-started",
        "registration_complete": "not-started",
        "store_details_complete": "not-started",
        "documents_uploaded": "not-started",
    }

    # Check profile
    user_profile = UserProfile.query.filter_by(id=user_id).first()
    if user_profile:
        progress["profile_complete"] = "completed"

    # Registration form
    reg_form = RegistrationForm.query.filter_by(user_id=user_id).first()
    if reg_form:
        progress["registration_complete"] = "completed"

    # Store details
    store_details = StoreDetails.query.filter_by(owner_id=user_id).first()
    if store_details:
        reg_status = store_details.reg_status
        if reg_status == 'registered':
            progress["store_details_complete"] = "completed"
        elif reg_status in ['draft', 'submitted']:
            progress["store_details_complete"] = "started"

    # Documents
    documents = Document.query.filter_by(user_id=user_id).first()
    if documents:
        if documents.reviewed_status == "approved":
            progress["documents_uploaded"] = "completed"
        elif documents.submitted_status =="submitted" and documents.reviewed_status =="pending":
            progress["documents_uploaded"] = "started"
        else :
            progress["documents_uploaded"] = "not-started"

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

    user_id = user_profile.id
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
            existing_owner = SpazaOwner.query.filter_by(user_id=user_id).first()
            if not existing_owner:
                new_owner = SpazaOwner(
                    name=first_name.strip(),
                    surname=last_name.strip(),
                    email=email,
                    address=street_address.strip(),
                    said=id_number.strip() if id_number else 'N/A',
                    user_id=user_id
                )
                db.session.add(new_owner)
                db.session.commit()
                flash('Spaza Owner registration successful!', category='success')
                print(f"✅ SpazaOwner created: {new_owner}")
            else:
                flash('Spaza Owner already exists.', category='info')
                print(f"ℹ️ Existing SpazaOwner found for User ID: {user_id}")

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred during owner registration: {str(e)}", category='error')
            print(f"❌ Error during SpazaOwner creation: {str(e)}")
            return redirect(url_for('spachainauth.spachainauth_register'))

        try:
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
            db.session.commit()
            flash('Main registration successful!', category='success')
            print(f"✅ RegistrationForm created: {registration}")
            return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=user_id))

        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred during registration: {str(e)}", category='error')
            print(f"❌ Error during RegistrationForm creation: {str(e)}")
            return redirect(url_for('spachainauth.spachainauth_register'))

    return render_template('spachainauth_register.html', title='Spaza Owner Registration')

# route for home and profile routes for registered users

"""@spachainauth.route('/home', methods=['GET', 'POST'])
@login_required
def spachainauth_home():
    
    return render_template("spachainauth_home.html", user=current_user) """

# route to retun=rn the logged on user to the their dashboard
@spachainauth.route('/home')
@login_required
def spachainauth_home():
    
    print("reached spa chain auth home now now")
    spaza_owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()
    
    # Initialize store variable to None as a fallback
    store = None
    progress = get_registration_progress(current_user.id)  # Fetch progress data ✅

    if spaza_owner:
        
        # Query for the store details
        store = StoreDetails.query.filter_by(owner_id=spaza_owner.id).first()
        
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

    return render_template("spachainauth_home.html", user=current_user, store=store, progress=progress)  # ✅ Pass progress

# owner details for the spaza shop owner
@spachainauth.route('/owner-details/<int:user_id>', methods=['GET', 'POST'])
@login_required
def spachainauth_owner_details(user_id):
    #user = UserProfile.query.get(user_id)
    user = UserProfile.query.filter_by(id=user_id).first()

    if not user:
        flash('No user profile exists. Ensure your registration is completed.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))
    
    registration = RegistrationForm.query.filter_by(user_id=user_id).first()
    if not registration:
        flash('No registration details found. Please complete the registration form first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_register', user_id=user_id)) 

    owner = None

    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        surname = request.form.get('surname')
        email = request.form.get('email')
        address = request.form.get('address')
        said = request.form.get('said')

        # Check if owner details already exist for this user
        owner = SpazaOwner.query.filter_by(user_id=user.id).first()
        if owner:
            flash('Owner details already exist.', category='error')
            return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=owner.user_id))

        # Add new owner details
        new_owner = SpazaOwner(
            user_id=user.id,
            name=name,
            surname=surname,
            email=email,
            address=address,
            said=said
        )
        db.session.add(new_owner)
        db.session.commit()
        flash('Owner details saved successfully!', category='success')
        return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=new_owner.user_id))

    # GET request — correctly fetch owner using user_id
    owner = SpazaOwner.query.filter_by(user_id=user.id).first()

    return render_template("spachainauth_owner_details.html", user=user, owner=owner,registration=registration)


# define a route to make spaza owner available to all templates

@spachainauth.context_processor
def inject_spaza_owner():
    if current_user.is_authenticated:
        owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()
        return dict(spaza_owner=owner)
    return dict(spaza_owner=None)  



# route for the owner to be able to regisyte the store details
@spachainauth.route('/store', methods=['GET', 'POST'])
@login_required
def spachainauth_store():


     # get the current user profile first
    user_id = current_user.id
    user_profile = UserProfile.query.filter_by(id=user_id).first()
    if not user_profile:
        flash('No user profile found. Please complete your profile first.', category='error')
        return redirect(url_for('naledi.naledi_sign_up'))
    
    #step 2 : check for the owner details
    spaza_owner = SpazaOwner.query.filter_by(user_id=user_id).first()
    
    existing_stores =[]
    
    # if user registration form is not completed, redirect to the registration form
    if not spaza_owner:
        flash('You need to complete your registration. Please complete owner details first.', category='error')
        return redirect(url_for('spachainauth.spachainauth_register'))
        #return redirect(url_for('spachainauth.spachainauth_owner_details', user_id=user_id))
    
    # for the exsting owner m check existing stores
    existing_stores = StoreDetails.query.filter_by(owner_id=spaza_owner.id).all()


    if request.method == 'POST':
        # Extract common store fields
        user_id = current_user.id
        storetype = request.form.get('storetype')
        store_name = request.form.get('store_name')
        storevolume = request.form.get('storevolume')
        cicpno = request.form.get('cicpno')
        sarsno = request.form.get('sarsno')
        permitid = request.form.get('permitid')
        zonecertno = request.form.get('zonecertno')
        #compstatus = request.form.get('compstatus')
        ownershipstatus = request.form.get('ownershipstatus')
        storeaddress = request.form.get('storeaddress')
        city = request.form.get('city')
        postal_code = request.form.get('postal_code')
        province = request.form.get('province')
        district_mnc = request.form.get('municipality')

        # Extract Lessee fields if ownership status is Rented
        leseefname = request.form.get('leseefname')
        leseelname = request.form.get('leseelname')
        lesee_id = request.form.get('lesee_id')

        # Validate missing store fields
        required_fields = {
            "Store Type": storetype, "Store Name": store_name, "Store Volume": storevolume,
            "CIPC Number": cicpno, "SARS Number": sarsno, "Permit ID": permitid,
            "Zoning Certification": zonecertno, 
            "Ownership Status": ownershipstatus, "Store Address": storeaddress,
            "City": city, "Postal Code": postal_code, "Province": province, "District": district_mnc
        }

        print(f"Store details: {required_fields}")

        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            flash(f"Store related Data missing. Please provide values for: {', '.join(missing_fields)}", category='error')
            return redirect(url_for('spachainauth.spachainauth_store'))
         
        # Validate missing lessee fields
        required_lessee_fields = {"Lessee First Name": leseefname, "Lessee Last Name": leseelname, "Lessee ID": lesee_id}
        missing_lessee_fields = [field for field, value in required_lessee_fields.items() if not value]

        print(f"Lesee details: {required_lessee_fields}")
        
        # If ownership status is rented, lessee details are required
        """if ownershipstatus == "Rented":
            if missing_lessee_fields:
                flash(f"Please provide the Store Renter's details: {', '.join(missing_lessee_fields)}", category='error')
                return redirect(url_for('spachainauth.register_store'))"""


       
        

        progress = get_registration_progress(current_user.id)  # Fetch progress data ✅
        # Create store record
        try:
    
            store = StoreDetails(
                storetype=storetype.strip(),
                store_name=store_name.strip(),
                storevolume=storevolume.strip(),
                cicpno=cicpno.strip(),
                sarsno=sarsno.strip(),
                permitid=permitid.strip(),
                zonecertno=zonecertno.strip(),
                compstatus="submitted status",
                ownershipstatus=ownershipstatus.strip(),
                storeaddress=storeaddress.strip(),
                city=city.strip(),
                postal_code=postal_code.strip(),
                province=province.strip(),
                district_mnc=district_mnc.strip(),
                owner_id=spaza_owner.id
            )
            db.session.add(store)
            db.session.commit() # commit to generate store.id
            flash("Store details saved successfully!", category="success")

        # Create Lessee record if ownership status is Rented
            if ownershipstatus == "Rented":
                if missing_lessee_fields:
                    flash(f"Please provide the Store Renter's details: {', '.join(missing_lessee_fields)}", category='error')
                    return redirect(url_for('spachainauth.spachainauth_store'))
                else:
                            new_lesee = Lesee(
                                leseefname=leseefname.strip(),
                                leseelname=leseelname.strip(),
                                lesee_id=lesee_id.strip(),
                                leseeemail="draft@example.com",
                                leseeaddress="draft address",
                                leseestoreid=store.id,  # Link to the newly created store
                                spazaownerid=spaza_owner.id  # Link to the spaza owner
                            )
                            db.session.add(new_lesee)
                            db.session.commit()      # create a new lessee record using the store.id             
                            flash("Lesee details saved successfully!", category="success")
                            
            return redirect(url_for('spachainauth.spachainauth_home',user=current_user))
        except Exception as e:
            db.session.rollback()
            flash(f"Error saving lessee details: {str(e)}", category="error")
            return redirect(url_for('spachainauth.spachainauth_store',user=current_user,progress=progress))

    # Handle non-POST requests
    return render_template( 'spachainauth_store.html', title='Spaza Owner Registration',user=current_user,
                                existing_stores=existing_stores
                            )


#Define to help determine if there are exsiting store for a registered owner
@spachainauth.route('/store_manage', methods=['GET'])
@login_required
def spachainauth_store_manage():
    user_id = current_user.id
    spaza_owner = SpazaOwner.query.filter_by(user_id=user_id).first()

    existing_stores = []
    if spaza_owner:
        existing_stores = StoreDetails.query.filter_by(owner_id=spaza_owner.id).all()

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
            user_id=current_user.id,
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
    user_id = current_user.id

    print(f"Health Compliance User ID: {user_id}")

    owner = SpazaOwner.query.filter_by(user_id=user_id).first()
    if not owner:
        flash('Owner details not found. Please complete owner details first.', category='error')
        return redirect(url_for('spachainauth.owner_details', user_id=current_user.id))

    print(f"health Owner ID: {owner.id}")
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
            user_id=current_user.id,
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
    user_id = current_user.id

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
    user_id = current_user.id
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
   
    owner = SpazaOwner.query.filter_by(user_id=current_user.id).first()

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
            owner = SpazaOwner(user_id=current_user.id)
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
    user_profile = UserProfile.query.get(current_user.id)
    
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
    existing_docs = {doc.document_type: doc for doc in Document.query.filter_by(user_id=current_user.id).all()}

    if request.method == 'POST':
        for field_name, document_type in document_types.items():
            file = request.files.get(field_name)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                destination_blob_name = f'{current_user.id}/{document_type}_{filename}'
                file_url = upload_to_gcs(file, destination_blob_name)

                if document_type in existing_docs:
                    # ✅ Update existing document
                    existing_docs[document_type].file_url = file_url
                    existing_docs[document_type].filename = filename
                else:
                    # ✅ Add new document
                    new_document = Document(
                        user_id=current_user.id,
                        document_type=document_type,
                        file_url=file_url,
                        filename=filename,
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
    existing_docs = {doc.document_type: doc for doc in Document.query.filter_by(user_id=current_user.id).all()}
    
    if request.method == 'POST':
        for field_name, document_type in document_types.items():
            file = request.files.get(field_name)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                destination_blob_name = f'{current_user.id}/{document_type}_{filename}'
                file_url = upload_to_gcs(file, destination_blob_name)

                if document_type in existing_docs:
                    # ✅ Update existing document
                    existing_docs[document_type].file_url = file_url
                    existing_docs[document_type].filename = filename
                else:
                    # ✅ Add new document (shouldn't happen here, but as a fallback)
                    new_document = Document(
                        user_id=current_user.id,
                        document_type=document_type,
                        file_url=file_url,
                        filename=filename
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
    existing_docs = {doc.document_type for doc in Document.query.filter_by(user_id=current_user.id).all()}

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
    documents = Document.query.filter_by(user_id=user_id).all()

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

# Route to displace compliance status  for the store owner. The compliance excerciser is performed by the health inspector
# and the store owner is notified of the compliance status
# Route to display health compliance actions for the store owner
@spachainauth.route('/health_compliance')
@login_required
def health_compliance():
    print("reached health compliance")
    # Check if the user has a profile or services to display
    user_profile = UserProfile.query.get(current_user.id)
    if not user_profile:
        # If no profile exists, redirect to registration or an appropriate page
        flash("Please complete your profile to access services.", category="warning")
        return redirect(url_for('spachainauth.sign_up'))
   
    compliance_data = get_health_compliance_data(current_user.id)
    if not compliance_data:
        flash("No health compliance data found.", category="warning")
        #return redirect(url_for('spachainauth.spachainauth_health_self_check'))

    return render_template("spachainauth_health_compliance.html", user=current_user,compliance_data=compliance_data)




def get_fire_comoliance_data(user_id):
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
     user_profile = UserProfile.query.get(current_user.id)
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
    dashboard_data = generate_doc_status_dashboard(current_user.id)

    # Fetch health compliance data
    compliance_data = get_health_compliance_data(current_user.id)

    print(f"Dashboard Data: {compliance_data}")

    # Render the template with the dashboard data
    return render_template('spachainauth_dashboard.html',
                           submitted_docs=dashboard_data["submitted_documents"],
                           compliance_data=compliance_data,
                           registration_progress=dashboard_data["registration_progress"])



