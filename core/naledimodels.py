#from . import db
from datetime import datetime, timedelta
from flask_login import UserMixin
from sqlalchemy import Table, Column, Integer, String, MetaData
from sqlalchemy.sql import func
from flask_sqlalchemy import SQLAlchemy
from .extensions import db
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email

#db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    #notes = db.relationship('Note')
    
    def __repr__(self):
        return f'<User {self.email}>'


class UserProfile(db.Model, UserMixin):
    __tablename__ = 'user_profile'

    user_profile_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)                   # required for standard process
    cellno = db.Column(db.String(100), unique=True, nullable=False)
    user_password = db.Column(db.String(512), nullable=False)                        # required for standard process 
    is_social_login_user = db.Column(db.Boolean, default=False, nullable=False)            # Flag for Google users
    user_type = db.Column(db.String(50), nullable=False)                             # "spaza_owner" or "mnc_official"
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_verified = db.Column(db.Boolean, default=False)                                 # Email verification flag
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)           # Foreign key to User table
   

    # Relationship to SpazaOwner
    #spaza_owners = db.relationship('SpazaOwner', back_populates='user', cascade='all, delete')
    spaza_owner = db.relationship("SpazaOwner", back_populates="user_profile", uselist=False)

    def set_password(self, password):
        self.user_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.user_password, password)

    def get_id(self):
        return str(self.user_profile_id)

    def generate_reset_token(self, expires_sec=3600):
         s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
         return s.dumps(self.user_profile_id, salt='reset-password')

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='reset-password', max_age=max_age)
        except Exception:
            return None
        return UserProfile.query.get(user_id)
    @property
    def user_id(self):
        return self.user_profile_id

    def __repr__(self):
        return f'<UserProfile {self.username}>'
    
    def get_id(self):
       return str(self.user_profile_id)




class UserProfileForm(FlaskForm):
    name = StringField("First Name", validators=[DataRequired()])
    surname = StringField("Surname", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    cellno = StringField("Cell Number", validators=[DataRequired()])
    submit = SubmitField("Update Profile")


class RegistrationForm(db.Model,UserMixin):
    __tablename__ = "registration_form"
    reg_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_profile.user_profile_id', ondelete='CASCADE'), nullable=False)
    personal_details_complete = db.Column(db.Boolean, default=False)
    address_details_complete = db.Column(db.Boolean, default=False)
    business_type = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100),nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    dob = db.Column(db.DateTime, nullable=False)
    gender = db.Column(db.String(10),   nullable=False)
    id_number = db.Column(db.String(13),  nullable=False)  # South African ID number
    passport_number = db.Column(db.String(20), nullable=True)
    citizenship = db.Column(db.String(50), nullable=False)
    street_address = db.Column(db.String(100),  nullable=False)
    address2 = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(10),  nullable=False)
    province = db.Column(db.String(50), nullable=False)
    district_mnc = db.Column(db.String(50), nullable = False)  # District municipality
    status = db.Column(db.String(50), default="draft")  # "draft" or "submitted"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    user = db.relationship('UserProfile', backref='registration_form')
    spaza_owner = db.relationship("SpazaOwner", back_populates="registration_form", uselist=False)

class RegistrationProgress(db.Model):
    __tablename__ = "registration_progress"

    reg_proc_id = db.Column(db.Integer, primary_key=True)  # Unique ID for the progress entry
    user_profile_id = db.Column(db.Integer, db.ForeignKey('user_profile.user_profile_id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('spazaowner.owner_id'), nullable=True)  # Nullable initially
    form_id = db.Column(db.Integer, db.ForeignKey('registration_form.reg_id'), nullable=False)

    # Progress tracking fields
    personal_details_completed = db.Column(db.Boolean, default=False)
    address_details_completed = db.Column(db.Boolean, default=False)
    business_details_completed = db.Column(db.Boolean, default=False)
    overall_status = db.Column(db.String(50), default="in_progress")  # "in_progress" or "completed"

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('UserProfile', backref='registration_progress')
    owner = db.relationship('SpazaOwner', backref='registration_progress')
    form = db.relationship('RegistrationForm', backref='registration_progress')

    def __repr__(self):
        return f'<RegistrationProgress user_profile_id={self.user_profile_id}, status={self.overall_status}>'



class SpazaOwner(db.Model, UserMixin):
    __tablename__ = 'spazaowner'

    owner_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.String(100), nullable=False)
    said = db.Column(db.String(20), nullable=False)

    user_profile_id = db.Column(db.Integer, db.ForeignKey('user_profile.user_profile_id'), nullable=False)
    reg_id = db.Column(db.Integer, db.ForeignKey('registration_form.reg_id', ondelete='CASCADE'), nullable=False)

    user_profile = db.relationship("UserProfile", back_populates="spaza_owner")
    registration_form = db.relationship("RegistrationForm", back_populates="spaza_owner", uselist=False)

    # ✅ Relationship to stores
    stores = db.relationship("StoreDetails", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SpazaOwner {self.name} {self.surname}>'

    @property
    def full_name(self):
        return f"{self.name} {self.surname}"




class Lesee(db.Model, UserMixin):
    __tablename__ = 'lesee'

    lesee_id = db.Column(db.Integer, primary_key=True)
    leseefname = db.Column(db.String(45), nullable=False)
    leseelname = db.Column(db.String(45), nullable=False)
    leseeemail = db.Column(db.String(45), unique=True, nullable=False)
    leseeaddress = db.Column(db.String(45), nullable=False)
    lesee_id_no = db.Column(db.String(45), nullable=False)  # Identity number or document ID
    leseestoreid = db.Column(db.Integer, db.ForeignKey('store_details.store_id'), nullable=False)  # Links to StoreDetails
    owner_id = db.Column(db.Integer, db.ForeignKey('spazaowner.owner_id'), nullable=False)  # Links to SpazaOwner

    # Relationships
    store = db.relationship('StoreDetails', backref='lesee')  # Allows accessing lessee from a store
    owner = db.relationship('SpazaOwner', backref='lesees')  # Allows accessing all lessees for an owner

    def __repr__(self):
        return f"<Lesee {self.leseefname} {self.lesseelname}>"


class StoreDetails(db.Model,UserMixin):
    __tablename__ = 'store_details'

    store_id = db.Column(db.Integer, primary_key=True)
    #store_id = db.Column(db.Integer, unique=True, nullable=False, server_default=db.text("nextval('store_details_store_id_seq')"))
    permit_id = db.Column(db.Integer, unique=True, nullable=False)
    cicpno = db.Column(db.String(13), unique=True, nullable=False)
    sarsno = db.Column(db.String(13), unique=True, nullable=False)
    zonecertno = db.Column(db.String(13), unique=True, nullable=False)
    storetype = db.Column(db.String(150), nullable=False)
    compstatus = db.Column(db.String(150), nullable=False)
    ownershipstatus = db.Column(db.String(150), nullable=False)
    storeaddress = db.Column(db.String(150), nullable=False)
    storevolume = db.Column(db.String(150), nullable=False)
    store_name = db.Column(db.String(150), nullable=False)
    reg_status = db.Column(db.String(10), default="draft")
    city = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(10),  nullable=False)
    province = db.Column(db.String(50), nullable=False)
    district_mnc = db.Column(db.String(50), nullable = False)  # District municipality
    owner_id = db.Column(db.Integer, db.ForeignKey('spazaowner.owner_id'), nullable=False)  # Match the actual table name
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


    owner = db.relationship("SpazaOwner", back_populates="stores")

    #def __repr__(self):
    #    return f"<StoreDetails {self.store_name}>"
    
    def __repr__(self):
        return f"<Store {self.store_name} ({self.store_id})>"
    

class FoodItems(db.Model):
    __tablename__ = 'food_items'

    food_item_id = db.Column(db.Integer, primary_key=True)
    fk_user_id = db.Column(db.Integer, db.ForeignKey('user_profile.user_profile_id'), nullable=False)  # Link to the user
    fk_store_id = db.Column(db.Integer, db.ForeignKey('store_details.store_id'), nullable=False)  # Link to the store
    selected_items = db.Column(db.JSON, nullable=True)  # Store selected food items as JSON
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f'<FoodItems {self.id}>'




class HealthCompliance(db.Model):
    __tablename__ = "health_compliance"

    health_comp_id = db.Column(db.Integer, primary_key=True)
    
    store_id = db.Column(db.Integer, db.ForeignKey('store_details.store_id'), nullable=False)  # ✅ Link to Store
    user_id = db.Column(db.Integer, db.ForeignKey('spazaowner.owner_id'), nullable=False)  # ✅ Spaza Owner
    official_id = db.Column(db.Integer, db.ForeignKey('mncusers.mnc_user_id'), nullable=False)  # ✅ Health Official
    
    sanitary_fac = db.Column(db.JSON)
    cleaning_fac = db.Column(db.JSON)
    hand_wash_fac = db.Column(db.JSON)
    waste_disp = db.Column(db.JSON)
    food_hand_fac = db.Column(db.JSON)
    food_store_fac = db.Column(db.JSON)
    foodprep_proc = db.Column(db.JSON)
    foodprep_tool = db.Column(db.JSON)
    employees = db.Column(db.JSON)
    compliance_status = db.Column(db.String(20), default="pending")  # 'pending', 'compliant', 'non-compliant'

    review_cycle_start = db.Column(db.Date, default=datetime.utcnow)
    review_cycle_end = db.Column(db.Date, default=lambda: datetime.utcnow() + timedelta(days=14))

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    # ✅ Define Relationships
    store = db.relationship("StoreDetails", backref="health_compliances")
    owner = db.relationship("SpazaOwner", backref="health_compliances")
    official = db.relationship("MncUser", backref="health_compliances")  # ✅ Health Official

    def __repr__(self):
        return f"<HealthCompliance Store={self.store_id}, Official={self.official_id}>"




# modified document model ti include statuses. This will help with update actions from the officials
class Document(db.Model):
    doc_id = db.Column(db.Integer, primary_key=True)
    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey('user_profile.user_profile_id'), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('mncusers.mnc_user_id'), nullable=True)  # Nullable initially
    document_type = db.Column(db.String(100), nullable=False)
    file_url = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # New columns for document statuses
    submitted_status = db.Column(db.String(20), default="pending")  # Values: "pending", "check", "warning"
    reviewed_status = db.Column(db.String(20), default="pending")   # Values: "pending", "check", "warning" 
    approved_status = db.Column(db.String(20), default="pending")   # Values: "pending", "check", "warning"

    user = db.relationship('UserProfile', backref=db.backref('documents', lazy=True))

    def __repr__(self):
        return f'<Document {self.filename}>'
    
#revised mncusers model to inclide SSO, password reset  and admin flags
class MncUser(db.Model, UserMixin):
    __tablename__ = "mncusers"

    mnc_user_id = db.Column(db.Integer, primary_key=True)
    deptid = db.Column(db.Integer, db.ForeignKey("mncdepartments.mnc_dept_id"), nullable=False)
    municipalid = db.Column(db.Integer, db.ForeignKey("municipal.mncid"), nullable=False)
    
    mncfname = db.Column(db.String(45), nullable=False)
    mnclname = db.Column(db.String(45), nullable=False)
    mncemail = db.Column(db.String(45), nullable=False, unique=True)
    mnccontact = db.Column(db.String(45), nullable=False, unique=True)
    mnctitle = db.Column(db.String(45), nullable=False)
    password_hash = db.Column(db.String(256))
    
    is_verified = db.Column(db.Boolean, default=False)
    is_sso_only = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    is_admin = db.Column(db.Boolean, default=False)
    force_password_reset = db.Column(db.Boolean, default=False)
    is_official = db.Column(db.Boolean)

    department = db.relationship("MncDepartment", back_populates="users")
    municipal = db.relationship("Municipal", back_populates="users")
    issued_permits = db.relationship("Permit", back_populates="issued_by")
    
    def get_id(self):
        return str(self.mnc_user_id)

    # optionally:
    @property
    def is_active(self):
        return True

    # ✅ Add is_active property
    # ✅ Add is_active property (Required for Flask-Login)
    @property
    def is_active(self):
        return True  # Change this if you need to disable users
    
    def set_password(self, password):
       """Hash and set the user's password."""
       self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)
    
    # ✅ Generate Password Reset Token
    def generate_reset_token(self, expires_sec=1800):
        """Generate a secure reset token (valid for `expires_sec` seconds)."""
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps({'user_id': self.id}, salt='password-reset')

    def __repr__(self):
        return f"<MncUser {self.mncfname} {self.mnclname} ({self.mncemail})>"
    

# model for the Municipal table

class Municipal(db.Model):
    __tablename__ = "municipal"

    mncid = db.Column(db.Integer, primary_key=True)
    mncname = db.Column(db.String(45), nullable=False)
    mncprov = db.Column(db.String(45), nullable=False)
    category = db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(45), nullable=False)

    departments = db.relationship("MncDepartment", back_populates="municipal", cascade="all, delete-orphan")
    users = db.relationship("MncUser", back_populates="municipal", cascade="all, delete-orphan")
    permits = db.relationship("Permit", back_populates="municipal")

    def __repr__(self):
        return f"<Municipal {self.mncname} ({self.mncid})>"
    





class MncDepartment(db.Model):
    __tablename__ = "mncdepartments"

    mnc_dept_id = db.Column(db.Integer, primary_key=True)
    deptname = db.Column(db.String(45), nullable=False)
    compliancetype = db.Column(db.String(45), nullable=False)
    complianceactions = db.Column(db.String(45), nullable=False)
    mncid = db.Column(db.Integer, db.ForeignKey("municipal.mncid", ondelete="CASCADE"), nullable=False)

    municipal = db.relationship("Municipal", back_populates="departments")
    users = db.relationship("MncUser", back_populates="department")



       
    
# model for the Mncdepartments table
class Permit(db.Model):
    __tablename__ = "permit"

    permit_id = db.Column(db.Integer, primary_key=True)
    storename = db.Column(db.String(45), nullable=False)
    permittype = db.Column(db.String(45), nullable=False)
    issuedate = db.Column(db.DateTime, nullable=False)
    expirydate = db.Column(db.DateTime, nullable=False)
    permitstatus = db.Column(db.String(45), nullable=False)
    storeclass = db.Column(db.String(45), nullable=False)

    mncid = db.Column(db.Integer, db.ForeignKey("municipal.mncid"), nullable=False)
    storeid = db.Column(db.Integer, nullable=False)
    permitnumber = db.Column(db.String(45), nullable=False, unique=True)
    
    createdat = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    updatedat = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    issued_by_mnc_id = db.Column(db.Integer, db.ForeignKey("mncusers.mnc_user_id"))

    municipal = db.relationship("Municipal", back_populates="permits")
    issued_by = db.relationship("MncUser", back_populates="issued_permits")


#identity verification model to realise the identity of the spaza owners
class IdentityVerification(db.Model):
    __tablename__ = "identity_verification"

    ver_id = db.Column(db.Integer, primary_key=True)

    owner_verified_id = db.Column(db.String(15), nullable=False)
    lesee_verified_id = db.Column(db.String(15), nullable=False)
    store_verified_cipc = db.Column(db.String(15), nullable=False)
    store_verified_tax = db.Column(db.String(15), nullable=False)
    police_clearance_id = db.Column(db.String(15), nullable=False)

    spaza_owner_id = db.Column(db.Integer, db.ForeignKey('spazaowner.owner_id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('mncusers.mnc_user_id'), nullable=True)
    approval_datetime = db.Column(db.DateTime, default=datetime.utcnow)

    spaza_owner = db.relationship("SpazaOwner", backref="identity_verifications")
    approver = db.relationship("MncUser", backref="approvals_made")

# model for municipal compliance  - enables logic for approvals by municipal officials
class MunicipalCompliance(db.Model):
    __tablename__ = "municipal_compliance"

    mnc_comp_id = db.Column(db.Integer, primary_key=True)

    verified_coa = db.Column(db.String(15), nullable=False)
    verified_fire_insp = db.Column(db.String(15), nullable=False)
    verified_zoning_cert = db.Column(db.String(15), nullable=False)
    verified_elec_cert = db.Column(db.String(15), nullable=False)
    verified_building_cert = db.Column(db.String(15), nullable=False)

    spaza_owner_id = db.Column(db.Integer, db.ForeignKey("spazaowner.owner_id"), nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey("mncusers.mnc_user_id"), nullable=True)
    verified_at = db.Column(db.DateTime, default=datetime.utcnow)

    spaza_owner = db.relationship("SpazaOwner", backref="municipal_compliance_records")
    verified_official = db.relationship("MncUser", backref="compliance_verifications")

