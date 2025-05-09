# Standard Library Imports
from typing import List, Optional
from datetime import datetime, timedelta
import enum
import os
import shutil
from uuid import uuid4
from pathlib import Path
import csv
from io import StringIO
from contextlib import asynccontextmanager
import uuid
import qrcode
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import jwt
from datetime import datetime, timedelta, timezone


# FastAPI and Related Imports
from fastapi import FastAPI, Depends, HTTPException, Request, status, File, UploadFile, Form, APIRouter, BackgroundTasks 
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# Database and ORM Imports
from sqlalchemy.orm import Session, relationship, declarative_base
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, create_engine, text
from sqlalchemy.sql import func
from databases import Database

# Authentication and Security Imports
import jwt
from passlib.context import CryptContext

# Configuration and Validation Imports
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
database = Database(DATABASE_URL)
Base = declarative_base()
engine = create_engine(DATABASE_URL)

# Password hashing and JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Set up upload directory for trainee photos
UPLOAD_DIR = Path("uploads/trainee_photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Create router
certificate_router = APIRouter(prefix="/certificates", tags=["certificates"])

# Enums
class PaymentType(str, enum.Enum):
    CASH = "Cash"
    CREDIT = "Credit"

class TrainingStatus(str, enum.Enum):
    PENDING = "Pending"
    CONFIRMED = "Confirmed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class TrainerType(str, enum.Enum):
    EMPLOYEE = "Employee"
    FREELANCER = "Freelancer"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    contact_person = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    
    training_registrations = relationship("TrainingRegistration", back_populates="customer")

class TrainingCourse(Base):
    __tablename__ = "training_courses"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    duration_hours = Column(Float)
    
    training_registrations = relationship("TrainingRegistration", back_populates="training_course")

class Trainer(Base):
    __tablename__ = "trainers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)  # Employee or Freelancer
    charge_per_hour = Column(Float)
    contact_number = Column(String)
    phone = Column(String)
    email = Column(String)
    address = Column(String)
    gov_id_number = Column(String)
    
    training_registrations = relationship("TrainingRegistration", back_populates="trainer")

class TrainingCertification(Base):
    __tablename__ = "training_certifications"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    validity_days = Column(Integer)
    
    training_registrations = relationship("TrainingRegistration", back_populates="training_certification")

class TrainingRegistration(Base):
    __tablename__ = "training_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    registration_number = Column(String, unique=True, index=True)
    request_date = Column(Date, default=datetime.now().date)
    request_receiver = Column(String)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer_point_of_contact = Column(String)
    training_course_id = Column(Integer, ForeignKey("training_courses.id"))
    num_trainees = Column(Integer, default=0)
    unit_rate_kd = Column(Float)
    total_amount_kd = Column(Float)
    payment_type = Column(String)
    trainer_id = Column(Integer, ForeignKey("trainers.id"))
    training_date = Column(Date)
    training_time = Column(String, nullable=True)
    training_certification_id = Column(Integer, ForeignKey("training_certifications.id"), nullable=True)
    status = Column(String, default=TrainingStatus.PENDING)
    remarks = Column(String, nullable=True)
    training_venue = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    customer = relationship("Customer", back_populates="training_registrations")
    training_course = relationship("TrainingCourse", back_populates="training_registrations")
    trainer = relationship("Trainer", back_populates="training_registrations")
    training_certification = relationship("TrainingCertification", back_populates="training_registrations")
    trainees = relationship("Trainee", back_populates="training_registration")


class Trainee(Base):
    __tablename__ = "trainees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    civil_id = Column(String, index=True)  # Civil ID or Employee ID
    company_name = Column(String)
    photo_path = Column(String, nullable=True)  # Path to stored photo
    training_registration_id = Column(Integer, ForeignKey("training_registrations.id"), nullable=True)
    training_completion_date = Column(Date, nullable=True)
    certificate_validation_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    training_registration = relationship("TrainingRegistration", back_populates="trainees")

# Pydantic Models
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    model_config = ConfigDict(from_attributes=True)

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    is_active: bool
    is_admin: bool

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class CustomerBase(BaseModel):
    name: str
    contact_person: str
    email: EmailStr
    phone: str
    address: str
    model_config = ConfigDict(from_attributes=True)

class CustomerCreate(CustomerBase):
    pass

class CustomerOut(CustomerBase):
    id: int

class TrainingCourseBase(BaseModel):
    title: str
    description: str
    duration_hours: float
    model_config = ConfigDict(from_attributes=True)

class TrainingCourseCreate(TrainingCourseBase):
    pass

class TrainingCourseOut(TrainingCourseBase):
    id: int

class TrainerBase(BaseModel):
    name: str
    type: TrainerType
    charge_per_hour: float
    contact_number: str
    phone: str
    email: EmailStr
    address: str
    gov_id_number: str
    model_config = ConfigDict(from_attributes=True)

class TrainerCreate(TrainerBase):
    pass

class TrainerOut(TrainerBase):
    id: int

class TrainingCertificationBase(BaseModel):
    name: str
    description: str
    validity_days: int
    model_config = ConfigDict(from_attributes=True)

class TrainingCertificationCreate(TrainingCertificationBase):
    pass

class TrainingCertificationOut(TrainingCertificationBase):
    id: int

class TrainingRegistrationBase(BaseModel):
    request_receiver: str
    customer_id: int
    customer_point_of_contact: str
    training_course_id: int
    num_trainees: Optional[int] = 0
    unit_rate_kd: float
    total_amount_kd: float
    payment_type: PaymentType
    trainer_id: int
    training_date: datetime
    training_time: Optional[str] = None
    training_certification_id: Optional[int] = None
    remarks: Optional[str] = None
    training_venue: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class TrainingRegistrationCreate(TrainingRegistrationBase):
    pass

class TrainingRegistrationOut(TrainingRegistrationBase):
    id: int
    registration_number: str
    request_date: datetime
    status: TrainingStatus
    created_at: datetime
    updated_at: datetime
    training_course: Optional[TrainingCourseOut] = None  # Add this line
    model_config = ConfigDict(from_attributes=True)

class TraineeBase(BaseModel):
    name: str
    civil_id: str
    company_name: str
    training_completion_date: Optional[datetime] = None
    certificate_validation_date: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class TraineeCreate(TraineeBase):
    photo: Optional[UploadFile] = None

class TraineeOut(TraineeBase):
    id: int
    photo_path: Optional[str] = None
    training_registration_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TrainingRegistrationConfirmationBase(BaseModel):
    training_registration_id: int
    training_date: datetime
    training_time: str
    trainer_id: int
    training_venue: str
    remarks: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class TrainingRegistrationConfirmationCreate(TrainingRegistrationConfirmationBase):
    pass

class TrainingRegistrationConfirmationOut(BaseModel):
    id: int
    registration_number: str
    training_date: datetime
    training_time: str
    trainer_name: str
    customer_name: str
    training_course_title: str
    num_trainees: int
    unit_rate_kd: float
    total_amount_kd: float
    training_venue: str
    status: TrainingStatus
    remarks: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class CertificateVerificationResponse(BaseModel):
    is_valid: bool
    trainee_name: Optional[str] = None
    trainee_id: Optional[str] = None
    company_name: Optional[str] = None
    course_title: Optional[str] = None
    training_date: Optional[str] = None
    expiry_date: Optional[str] = None
    registration_number: Optional[str] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Model for certificate generation request
class CertificateGenerationRequest(BaseModel):
    training_registration_id: int
    trainee_id: int
    model_config = ConfigDict(from_attributes=True)

# Model for certificate data
class Certificate(BaseModel):
    id: str  # Certificate number
    trainee_id: int
    registration_id: int
    issue_date: datetime
    expiry_date: Optional[datetime] = None
    certificate_path: Optional[str] = None
    is_revoked: bool = False
    revocation_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Add Certificate model to database models
class CertificateDB(Base):
    __tablename__ = "certificates"
    
    id = Column(String, primary_key=True)
    trainee_id = Column(Integer, ForeignKey("trainees.id"))
    registration_id = Column(Integer, ForeignKey("training_registrations.id"))
    issue_date = Column(DateTime, default=func.now())
    expiry_date = Column(DateTime, nullable=True)
    certificate_path = Column(String, nullable=True)
    is_revoked = Column(Boolean, default=False)
    revocation_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    trainee = relationship("Trainee", back_populates="certificates")
    registration = relationship("TrainingRegistration", back_populates="certificates")

# Pydantic models
class CertificateGenerateRequest(BaseModel):
    trainee_id: int
    training_registration_id: int

class CertificateResponse(BaseModel):
    id: str
    trainee_id: int
    registration_id: int
    issue_date: str
    expiry_date: Optional[str] = None
    is_revoked: bool = False
    revocation_reason: Optional[str] = None

class CertificateVerifyResponse(BaseModel):
    is_valid: bool
    trainee_name: Optional[str] = None
    trainee_id: Optional[str] = None
    company_name: Optional[str] = None
    course_title: Optional[str] = None
    training_date: Optional[str] = None
    expiry_date: Optional[str] = None
    registration_number: Optional[str] = None
    error_message: Optional[str] = None

# Add relationships to existing models
Trainee.certificates = relationship("CertificateDB", back_populates="trainee")
TrainingRegistration.certificates = relationship("CertificateDB", back_populates="registration")

# Ensure certificate directory exists
CERTIFICATE_DIR = Path("static/certificates")
CERTIFICATE_DIR.mkdir(parents=True, exist_ok=True)
# Helper Functions
def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_directories():
    # Create necessary directories
    directories = [
        Path("uploads/trainee_photos"),
        Path("static"),
        Path("uploads"),
        Path("logs")  # Additional directory for potential logging
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

# Function to generate certificate number
def generate_certificate_number(db: Session, registration_number: str, trainee_id: int) -> str:
    reg_number = registration_number.replace('TR-', '')
    random_id = uuid.uuid4().hex[:6]
    cert_number = f"IICTCM{reg_number}-{trainee_id}-{random_id}"
    
    # Ensure uniqueness
    existing = db.query(CertificateDB).filter(CertificateDB.id == cert_number).first()
    if existing:
        return generate_certificate_number(db, registration_number, trainee_id)
    
    return cert_number

# Function to generate QR code
def generate_qr_code(verification_url: str) -> Image:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    return qr_img

# Helper function to format date as DD-MM-YYYY
def format_date(date: datetime) -> str:
    if not date:
        return "N/A"
    return date.strftime("%d-%m-%Y")


# Background task to generate certificate image
def generate_certificate_image(
    cert_id: str,
    trainee_name: str,
    civil_id: str,
    company_name: str,
    course_title: str,
    training_date: datetime,
    expiry_date: Optional[datetime],
    photo_path: Optional[str],
    base_url: str,
    db: Session
) -> str:
    try:
        # Create a verification URL
        verification_url = f"{base_url}/certificates/verify/{cert_id}"
        
        # Generate QR code for verification
        qr_img = generate_qr_code(verification_url)
        
        # Try to load certificate template if it exists
        try:
            template = Image.open("static/certificate_template.jpg")
            width, height = template.size
        except FileNotFoundError:
            # Create a new image with white background if template doesn't exist
            width, height = 2000, 1414  # A4 landscape at 300 DPI
            template = Image.new('RGB', (width, height), (255, 255, 255))
        
        draw = ImageDraw.Draw(template)
        
        # Load fonts - try to use nice fonts if available, otherwise default
        try:
            title_font = ImageFont.truetype("arial.ttf", 80)
            subtitle_font = ImageFont.truetype("arial.ttf", 60)
            body_font = ImageFont.truetype("arial.ttf", 40)
            small_font = ImageFont.truetype("arial.ttf", 30)
        except (OSError, IOError):
            # Fallback to default font
            font_size_large = 40
            font_size_medium = 30
            font_size_small = 20
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            body_font = ImageFont.load_default() 
            small_font = ImageFont.load_default()
        
        # Draw INTREX logo if available
        try:
            logo = Image.open("static/intrex-logo.png")
            logo_width = int(width * 0.15)  # 15% of certificate width
            logo_height = int(logo.height * (logo_width / logo.width))
            logo = logo.resize((logo_width, logo_height))
            
            # Position logo at the top center
            logo_pos = ((width - logo_width) // 2, 50)
            template.paste(logo, logo_pos, logo.convert('RGBA'))
        except FileNotFoundError:
            # If logo not found, just add text
            draw.text((width // 2, 80), "INTERNATIONAL INSPECTION CENTRE CO. W.L.L.", 
                      fill=(0, 0, 0), font=subtitle_font, anchor="mm")
        
        # Draw certificate title
        y_pos = 200
        draw.text((width // 2, y_pos), "CERTIFICATE OF TRAINING", 
                  fill=(0, 0, 0), font=title_font, anchor="mm")
        
        y_pos += 100
        draw.text((width // 2, y_pos), "Proudly Presented to", 
                  fill=(0, 0, 0), font=subtitle_font, anchor="mm")
        
        # Add trainee photo if available
        photo_size = 200
        y_pos += 70
        photo_pos = ((width - photo_size) // 2, y_pos)
        
        if photo_path and os.path.exists(photo_path):
            try:
                trainee_photo = Image.open(photo_path)
                trainee_photo = trainee_photo.resize((photo_size, photo_size))
                template.paste(trainee_photo, photo_pos)
            except Exception as e:
                print(f"Error adding trainee photo: {e}")
                # Draw placeholder for photo
                draw.rectangle(
                    [photo_pos[0], photo_pos[1], photo_pos[0] + photo_size, photo_pos[1] + photo_size], 
                    outline=(0, 0, 0), width=2, fill=(240, 240, 240)
                )
                draw.text((width // 2, y_pos + photo_size // 2), "PHOTO", 
                          fill=(128, 128, 128), font=body_font, anchor="mm")
        else:
            # Draw placeholder for photo
            draw.rectangle(
                [photo_pos[0], photo_pos[1], photo_pos[0] + photo_size, photo_pos[1] + photo_size], 
                outline=(0, 0, 0), width=2, fill=(240, 240, 240)
            )
            draw.text((width // 2, y_pos + photo_size // 2), "PHOTO", 
                      fill=(128, 128, 128), font=body_font, anchor="mm")
        
        # Add trainee details
        y_pos += photo_size + 50
        draw.text((width // 2, y_pos), f"Mr. {trainee_name}",
                  fill=(0, 0, 0), font=subtitle_font, anchor="mm")
        
        y_pos += 60
        draw.text((width // 2, y_pos), f"({civil_id})",
                  fill=(0, 0, 0), font=body_font, anchor="mm")
        
        y_pos += 60
        draw.text((width // 2, y_pos), f"of {company_name}",
                  fill=(0, 0, 0), font=subtitle_font, anchor="mm")
        
        # Add course details
        y_pos += 80
        draw.text((width // 2, y_pos), f"is trained, assessed & certified in",
                  fill=(0, 0, 0), font=body_font, anchor="mm")
        
        y_pos += 60
        draw.text((width // 2, y_pos), f"{course_title}",
                  fill=(0, 0, 0), font=body_font, anchor="mm")
        
        y_pos += 60
        draw.text((width // 2, y_pos), f"on {format_date(training_date)}",
                  fill=(0, 0, 0), font=body_font, anchor="mm")
        
        if expiry_date:
            y_pos += 60
            draw.text((width // 2, y_pos), f"This certificate is valid up to {format_date(expiry_date)}",
                      fill=(0, 0, 0), font=body_font, anchor="mm")
        
        # Add signature lines
        y_pos += 120
        signature_line_y = y_pos + 30
        
        # Left signature
        left_sig_x = width // 4
        draw.text((left_sig_x, y_pos), "<<Signature>>",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        draw.line([(left_sig_x - 100, signature_line_y), (left_sig_x + 100, signature_line_y)],
                  fill=(0, 0, 0), width=2)
        
        draw.text((left_sig_x, signature_line_y + 40), "INTREX Official's Name",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        draw.text((left_sig_x, signature_line_y + 80), "For and on behalf of INTREX",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        
        # Right signature
        right_sig_x = width * 3 // 4
        draw.text((right_sig_x, y_pos), "<<Signature>>",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        draw.line([(right_sig_x - 100, signature_line_y), (right_sig_x + 100, signature_line_y)],
                  fill=(0, 0, 0), width=2)
        
        draw.text((right_sig_x, signature_line_y + 40), "Instructor Name",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        draw.text((right_sig_x, signature_line_y + 80), "Instructor",
                  fill=(0, 0, 0), font=small_font, anchor="mm")
        
        # Add QR code for verification
        qr_size = 150
        qr_img = qr_img.resize((qr_size, qr_size))
        qr_pos = (width - qr_size - 50, height - qr_size - 50)
        template.paste(qr_img, qr_pos)
        
        # Add certificate ID
        draw.text((width - 50, height - qr_size - 70), f"Certificate No: {cert_id}",
                  fill=(0, 0, 0), font=small_font, anchor="rs")
        
        # Add accreditation logos if available
        try:
            logos = Image.open("static/accreditation-logos.png")
            logos_width = width // 2
            logos_height = int(logos.height * (logos_width / logos.width))
            logos = logos.resize((logos_width, logos_height))
            
            logos_pos = ((width - logos_width) // 2, height - logos_height - 10)
            template.paste(logos, logos_pos, logos.convert('RGBA'))
        except FileNotFoundError:
            # If logos not available, just add text
            draw.text((width // 2, height - 30), "International Inspection Centre Co. W.L.L.",
                      fill=(128, 128, 128), font=small_font, anchor="mm")
        
        # Save the certificate as PDF
        certificate_filename = f"{cert_id}.pdf"
        certificate_path = CERTIFICATE_DIR / certificate_filename
        
        template.save(str(certificate_path), "PDF", resolution=300.0)
        
        # Update the database with the certificate path
        certificate = db.query(CertificateDB).filter(CertificateDB.id == cert_id).first()
        if certificate:
            certificate.certificate_path = str(certificate_path)
            db.commit()
        
        return str(certificate_path)
    except Exception as e:
        print(f"Error generating certificate image: {e}")
        raise

# New async function to create default users
async def create_default_users_async():
    db = Session(engine)
    try:
        # Create admin user if not exists
        admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
        admin_exists = db.query(User).filter(User.username == admin_username).first()
        if not admin_exists:
            admin_user = User(
                username=admin_username,
                email=os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com"),
                full_name="Admin User",
                hashed_password=get_password_hash(os.getenv("DEFAULT_ADMIN_PASSWORD", "adminpassword")),
                is_active=True,
                is_admin=True
            )
            db.add(admin_user)
            db.commit()
            print(f"Created default admin user: {admin_username}")
        
        # Create default regular user if not exists
        default_username = os.getenv("DEFAULT_USER_USERNAME", "user")
        default_user_exists = db.query(User).filter(User.username == default_username).first()
        if not default_user_exists:
            default_user = User(
                username=default_username,
                email=os.getenv("DEFAULT_USER_EMAIL", "user@example.com"),
                full_name="Default User",
                hashed_password=get_password_hash(os.getenv("DEFAULT_USER_PASSWORD", "userpassword")),
                is_active=True,
                is_admin=False
            )
            db.add(default_user)
            db.commit()
            print(f"Created default regular user: {default_username}")
        
        # Optional: Create some initial data for training courses, customers, etc.
        # Example for training courses
        default_course_exists = db.query(TrainingCourse).filter(TrainingCourse.title == "Initial Training Course").first()
        if not default_course_exists:
            default_course = TrainingCourse(
                title="Initial Training Course",
                description="Default training course created during system initialization",
                duration_hours=8.0
            )
            db.add(default_course)
            db.commit()
            print("Created default training course")
        
        # Optional: Create an initial customer
        default_customer_exists = db.query(Customer).filter(Customer.name == "Default Customer").first()
        if not default_customer_exists:
            default_customer = Customer(
                name="Default Customer",
                contact_person="Default Contact",
                email="contact@defaultcustomer.com",
                phone="1234567890",
                address="Default Address"
            )
            db.add(default_customer)
            db.commit()
            print("Created default customer")
    
    except Exception as user_creation_error:
        print(f"Error during user/default data creation: {user_creation_error}")
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_admin_user(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

def generate_registration_number(db: Session):
    current_year = datetime.now().year
    # Get the latest registration with current year prefix
    prefix = f"TR-{current_year}-"
    last_reg = db.query(TrainingRegistration)\
                .filter(TrainingRegistration.registration_number.like(f"{prefix}%"))\
                .order_by(TrainingRegistration.registration_number.desc())\
                .first()
    
    if last_reg is None:
        return f"{prefix}00001"
    
    last_number = int(last_reg.registration_number.split("-")[-1])
    new_number = last_number + 1
    return f"{prefix}{new_number:05d}"

def safe_mount_static_files(app: FastAPI):
    # Create directories if they don't exist
    static_dirs = ["static", "uploads"]
    for dir_path in static_dirs:
        dir_path = Path(dir_path)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Mount the directory
        try:
            app.mount(f"/{dir_path}", StaticFiles(directory=str(dir_path)), name=str(dir_path))
        except Exception as e:
            print(f"Error mounting {dir_path}: {e}")

# Fixed lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    try:
        # Create necessary directories
        create_directories()
        
        # Connect to database
        await database.connect()
        
        # Create database tables
        Base.metadata.create_all(bind=engine)
        
        # Create default users
        await create_default_users_async()
        
        print("Application startup completed successfully")
        yield
    
    except Exception as startup_error:
        print(f"Critical error during application startup: {startup_error}")
        yield
    
    finally:
        # Shutdown tasks
        try:
            # Disconnect from database
            await database.disconnect()
            print("Application is shutting down")
        except Exception as shutdown_error:
            print(f"Error during application shutdown: {shutdown_error}")

# Create FastAPI app instance
app = FastAPI(
    title="Training Registration System", 
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Authentication Routes
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# User Routes
@app.post("/users/", response_model=UserOut)
async def create_user(
    user: UserCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_admin_user)
):
    # Check if username already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Create new user
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me/", response_model=UserOut)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# Customer Routes
@app.post("/customers/", response_model=CustomerOut)
async def create_customer(
    customer: CustomerCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_customer = Customer(**customer.model_dump())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@app.get("/customers/", response_model=List[CustomerOut])
async def read_customers(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    customers = db.query(Customer).offset(skip).limit(limit).all()
    return customers

@app.get("/customers/{customer_id}", response_model=CustomerOut)
async def read_customer(
    customer_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if db_customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer

# Training Course Routes
@app.post("/training-courses/", response_model=TrainingCourseOut)
async def create_training_course(
    course: TrainingCourseCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_course = TrainingCourse(**course.model_dump())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

@app.get("/training-courses/", response_model=List[TrainingCourseOut])
async def read_training_courses(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    courses = db.query(TrainingCourse).offset(skip).limit(limit).all()
    return courses

@app.get("/training-courses/{course_id}", response_model=TrainingCourseOut)
async def read_training_course(
    course_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_course = db.query(TrainingCourse).filter(TrainingCourse.id == course_id).first()
    if db_course is None:
        raise HTTPException(status_code=404, detail="Training course not found")
    return db_course

# Trainer Routes
@app.post("/trainers/", response_model=TrainerOut)
async def create_trainer(
    trainer: TrainerCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_trainer = Trainer(**trainer.model_dump())
    db.add(db_trainer)
    db.commit()
    db.refresh(db_trainer)
    return db_trainer

@app.get("/trainers/", response_model=List[TrainerOut])
async def read_trainers(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    trainers = db.query(Trainer).offset(skip).limit(limit).all()
    return trainers

@app.get("/trainers/{trainer_id}", response_model=TrainerOut)
async def read_trainer(
    trainer_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if db_trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return db_trainer

# Training Certification Routes
@app.post("/training-certifications/", response_model=TrainingCertificationOut)
async def create_training_certification(
    certification: TrainingCertificationCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_certification = TrainingCertification(**certification.model_dump())
    db.add(db_certification)
    db.commit()
    db.refresh(db_certification)
    return db_certification

@app.get("/training-certifications/", response_model=List[TrainingCertificationOut])
async def read_training_certifications(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    certifications = db.query(TrainingCertification).offset(skip).limit(limit).all()
    return certifications

@app.get("/training-certifications/{certification_id}", response_model=TrainingCertificationOut)
async def read_training_certification(
    certification_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_certification = db.query(TrainingCertification).filter(TrainingCertification.id == certification_id).first()
    if db_certification is None:
        raise HTTPException(status_code=404, detail="Training certification not found")
    return db_certification

# Training Registration Routes
@app.post("/training-registrations/", response_model=TrainingRegistrationOut)
async def create_training_registration(
    registration: TrainingRegistrationCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    # Validate relationships
    customer = db.query(Customer).filter(Customer.id == registration.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    course = db.query(TrainingCourse).filter(TrainingCourse.id == registration.training_course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Training course not found")
    
    trainer = db.query(Trainer).filter(Trainer.id == registration.trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    
    if registration.training_certification_id:
        certification = db.query(TrainingCertification).filter(TrainingCertification.id == registration.training_certification_id).first()
        if not certification:
            raise HTTPException(status_code=404, detail="Training certification not found")
    
    # Generate registration number
    registration_number = generate_registration_number(db)
    
    # Create registration
    db_registration = TrainingRegistration(
        **registration.model_dump(),
        registration_number=registration_number,
        status=TrainingStatus.PENDING
    )
    
    db.add(db_registration)
    db.commit()
    db.refresh(db_registration)
    return db_registration


@app.get("/training-registrations/", response_model=List[TrainingRegistrationOut])
async def read_training_registrations(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    # Use joinedload to include the training_course information
    from sqlalchemy.orm import joinedload
    registrations = db.query(TrainingRegistration).options(
        joinedload(TrainingRegistration.training_course)
    ).offset(skip).limit(limit).all()
    return registrations

@app.get("/training-registrations/{registration_id}", response_model=TrainingRegistrationOut)
async def read_training_registration(
    registration_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_registration = db.query(TrainingRegistration).filter(TrainingRegistration.id == registration_id).first()
    if db_registration is None:
        raise HTTPException(status_code=404, detail="Training registration not found")
    return db_registration

# Trainee Routes
# Updated trainee endpoint making date fields completely optional
@app.post("/trainees/", response_model=TraineeOut)
async def create_trainee(
    name: str = Form(...),
    civil_id: str = Form(...),
    company_name: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        # Create trainee object with only required fields
        db_trainee = Trainee(
            name=name,
            civil_id=civil_id,
            company_name=company_name,
            # Dates are not included here so they will default to NULL in the database
        )
        
        # Handle photo upload if provided
        if photo and photo.filename:
            # Create a unique filename with original extension
            file_extension = os.path.splitext(photo.filename)[1]
            filename = f"trainee_{civil_id}_{uuid4()}{file_extension}"
            file_path = UPLOAD_DIR / filename
            
            # Ensure upload directory exists
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)
            
            # Store the file path
            db_trainee.photo_path = str(file_path)
        
        db.add(db_trainee)
        db.commit()
        db.refresh(db_trainee)
        return db_trainee
    
    except Exception as e:
        # Log the exception
        print(f"Error creating trainee: {str(e)}")
        
        # Rollback the transaction if an error occurred
        db.rollback()
        
        # Return a more detailed error
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create trainee: {str(e)}"
        )

@app.post("/trainees/{trainee_id}/assign-registration", response_model=TraineeOut)
async def assign_trainee_to_registration(
    trainee_id: int,
    registration_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Find the trainee
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    
    # Find the registration
    registration = db.query(TrainingRegistration).filter(TrainingRegistration.id == registration_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Training registration not found")
    
    # Check if trainee is already assigned to a registration
    if trainee.training_registration_id:
        raise HTTPException(status_code=400, detail="Trainee is already assigned to a registration")
    
    # Assign trainee to registration
    trainee.training_registration_id = registration_id
    
    # Increment the number of trainees in the registration
    registration.num_trainees += 1
    
    db.commit()
    db.refresh(trainee)
    return trainee

@app.get("/trainees/", response_model=List[TraineeOut])
async def read_trainees(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    trainees = db.query(Trainee).offset(skip).limit(limit).all()
    return trainees

@app.get("/trainees/unassigned", response_model=List[TraineeOut])
async def read_unassigned_trainees(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    unassigned_trainees = db.query(Trainee).filter(Trainee.training_registration_id == None).offset(skip).limit(limit).all()
    return unassigned_trainees

@app.get("/trainees/{trainee_id}", response_model=TraineeOut)
async def read_trainee(
    trainee_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    return trainee

@app.get("/training-registrations/{registration_id}/trainees", response_model=List[TraineeOut])
async def read_trainees_by_registration(
    registration_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    registration = db.query(TrainingRegistration).filter(
        TrainingRegistration.id == registration_id
    ).first()
    
    if not registration:
        raise HTTPException(status_code=404, detail="Training registration not found")
    
    trainees = db.query(Trainee).filter(
        Trainee.training_registration_id == registration_id
    ).all()
    
    return trainees

@app.put("/trainees/{trainee_id}", response_model=TraineeOut)
async def update_trainee(
    trainee_id: int,
    name: Optional[str] = Form(None),
    civil_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    training_completion_date: Optional[str] = Form(None),
    certificate_validation_date: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    
    # Update the fields if provided
    if name is not None:
        trainee.name = name
    
    if civil_id is not None:
        trainee.civil_id = civil_id
    
    if company_name is not None:
        trainee.company_name = company_name
    
    if training_completion_date is not None:
        try:
            trainee.training_completion_date = datetime.strptime(training_completion_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for training completion date. Use YYYY-MM-DD")
    
    if certificate_validation_date is not None:
        try:
            trainee.certificate_validation_date = datetime.strptime(certificate_validation_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for certificate validation date. Use YYYY-MM-DD")
    
    # Handle photo update if provided
    if photo and photo.filename:
        # Remove old photo if exists
        if trainee.photo_path and os.path.exists(trainee.photo_path):
            os.remove(trainee.photo_path)
        
        # Create a unique filename with original extension
        file_extension = os.path.splitext(photo.filename)[1]
        filename = f"trainee_{trainee.civil_id}_{uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
        
        # Update the file path
        trainee.photo_path = str(file_path)
    
    db.commit()
    db.refresh(trainee)
    return trainee

@app.delete("/trainees/{trainee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trainee(
    trainee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    
    # If trainee is assigned to a registration, decrement the trainee count
    if trainee.training_registration_id:
        registration = db.query(TrainingRegistration).filter(
            TrainingRegistration.id == trainee.training_registration_id
        ).first()
        if registration:
            registration.num_trainees = max(0, registration.num_trainees - 1)
    
    # Delete photo if exists
    if trainee.photo_path and os.path.exists(trainee.photo_path):
        os.remove(trainee.photo_path)
    
    db.delete(trainee)
    db.commit()
    return None

@app.get("/trainees/{trainee_id}/photo")
async def get_trainee_photo(
    trainee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    trainee = db.query(Trainee).filter(Trainee.id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    
    if not trainee.photo_path:
        raise HTTPException(status_code=404, detail="No photo available for this trainee")
    
    photo_path = Path(trainee.photo_path)
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found")
    
    return FileResponse(photo_path)

# Bulk upload functionality for trainees
@app.post("/bulk-trainees/", response_model=List[TraineeOut])
async def bulk_upload_trainees(
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Read CSV file
    content = await csv_file.read()
    string_io = StringIO(content.decode('utf-8-sig'))  # Handle BOM if present
    csv_reader = csv.DictReader(string_io)
    
    required_fields = ['name', 'civil_id', 'company_name']
    first_row = next(csv_reader, None)
    
    if not first_row:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    
    # Check if all required fields are present
    for field in required_fields:
        if field not in first_row:
            raise HTTPException(
                status_code=400, 
                detail=f"CSV file is missing required field: {field}"
            )
    
    # Process rows
    created_trainees = []
    string_io.seek(0)  # Reset to beginning of file
    next(csv_reader)  # Skip header row
    
    for row in csv_reader:
        # Optional date parsing
        completion_date = None
        validation_date = None
        
        if row.get('training_completion_date'):
            try:
                completion_date = datetime.strptime(row['training_completion_date'], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid training completion date for trainee {row['name']}"
                )
        
        if row.get('certificate_validation_date'):
            try:
                validation_date = datetime.strptime(row['certificate_validation_date'], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid certificate validation date for trainee {row['name']}"
                )
        
        # Create trainee
        db_trainee = Trainee(
            name=row['name'],
            civil_id=row['civil_id'],
            company_name=row['company_name'],
            training_completion_date=completion_date,
            certificate_validation_date=validation_date
        )
        
        db.add(db_trainee)
        created_trainees.append(db_trainee)
    
    db.commit()
    for trainee in created_trainees:
        db.refresh(trainee)
    
    return created_trainees

# Training Confirmation Routes
@app.post("/training-confirmations/", response_model=TrainingRegistrationConfirmationOut)
async def create_training_confirmation(
    confirmation: TrainingRegistrationConfirmationCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    # Get the registration
    registration = db.query(TrainingRegistration).filter(
        TrainingRegistration.id == confirmation.training_registration_id
    ).first()
    
    if not registration:
        raise HTTPException(status_code=404, detail="Training registration not found")
    
    # Validate trainer
    trainer = db.query(Trainer).filter(Trainer.id == confirmation.trainer_id).first()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    
    # Update registration with confirmation details
    registration.training_date = confirmation.training_date
    registration.training_time = confirmation.training_time
    registration.trainer_id = confirmation.trainer_id
    registration.training_venue = confirmation.training_venue
    registration.status = TrainingStatus.CONFIRMED
    
    if confirmation.remarks:
        registration.remarks = confirmation.remarks
    
    db.commit()
    db.refresh(registration)
    
    # Prepare response with joined data
    return {
        "id": registration.id,
        "registration_number": registration.registration_number,
        "training_date": registration.training_date,
        "training_time": registration.training_time,
        "trainer_name": trainer.name,
        "customer_name": registration.customer.name,
        "training_course_title": registration.training_course.title,
        "num_trainees": registration.num_trainees,
        "unit_rate_kd": registration.unit_rate_kd,
        "total_amount_kd": registration.total_amount_kd,
        "training_venue": registration.training_venue,
        "status": registration.status,
        "remarks": registration.remarks
    }

# Bulk upload functionality with registration assignment
@app.post("/bulk-upload/trainees", response_model=List[TraineeOut])
async def bulk_upload_trainees(
    csv_file: UploadFile = File(...),
    training_registration_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Read CSV file
    content = await csv_file.read()
    string_io = StringIO(content.decode('utf-8-sig'))  # Handle BOM if present
    csv_reader = csv.DictReader(string_io)
    
    # Validate registration if provided
    if training_registration_id:
        registration = db.query(TrainingRegistration).filter(
            TrainingRegistration.id == training_registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Training registration not found")
    
    # Required fields validation
    required_fields = ['name', 'civil_id', 'company_name']
    first_row = next(csv_reader, None)
    
    if not first_row:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    
    # Check if all required fields are present
    for field in required_fields:
        if field not in first_row:
            raise HTTPException(
                status_code=400, 
                detail=f"CSV file is missing required field: {field}"
            )
    
    # Process rows
    created_trainees = []
    string_io.seek(0)  # Reset to beginning of file
    next(csv_reader)  # Skip header row
    
    for row in csv_reader:
        # Optional date parsing
        completion_date = None
        validation_date = None
        
        if row.get('training_completion_date'):
            try:
                completion_date = datetime.strptime(row['training_completion_date'], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid training completion date for trainee {row['name']}"
                )
        
        if row.get('certificate_validation_date'):
            try:
                validation_date = datetime.strptime(row['certificate_validation_date'], "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid certificate validation date for trainee {row['name']}"
                )
        
        # Create trainee
        db_trainee = Trainee(
            name=row['name'],
            civil_id=row['civil_id'],
            company_name=row['company_name'],
            training_registration_id=training_registration_id,
            training_completion_date=completion_date,
            certificate_validation_date=validation_date
        )
        
        db.add(db_trainee)
        created_trainees.append(db_trainee)
    
    # Update trainee count in registration if applicable
    if training_registration_id:
        registration.num_trainees += len(created_trainees)
    
    db.commit()
    for trainee in created_trainees:
        db.refresh(trainee)
    
    return created_trainees

# Search and Filter Endpoints
@app.get("/search/trainees", response_model=List[TraineeOut])
async def search_trainees(
    name: Optional[str] = None,
    civil_id: Optional[str] = None,
    company_name: Optional[str] = None,
    training_registration_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Trainee)
    
    if name:
        query = query.filter(Trainee.name.ilike(f"%{name}%"))
    
    if civil_id:
        query = query.filter(Trainee.civil_id.ilike(f"%{civil_id}%"))
    
    if company_name:
        query = query.filter(Trainee.company_name.ilike(f"%{company_name}%"))
    
    if training_registration_id is not None:
        query = query.filter(Trainee.training_registration_id == training_registration_id)
    
    return query.offset(skip).limit(limit).all()

# Update training status
@app.put("/training-registrations/{registration_id}/status", response_model=TrainingRegistrationOut)
async def update_training_status(
    registration_id: int, 
    status: TrainingStatus, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_active_user)
):
    db_registration = db.query(TrainingRegistration).filter(TrainingRegistration.id == registration_id).first()
    if db_registration is None:
        raise HTTPException(status_code=404, detail="Training registration not found")
    
    db_registration.status = status
    db.commit()
    db.refresh(db_registration)
    return db_registration

# Dashboard Statistics Endpoint
@app.get("/dashboard/registration-stats")
async def get_registration_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Get total registrations
    total_registrations = db.query(TrainingRegistration).count()
    
    # Get completed registrations
    completed_registrations = db.query(TrainingRegistration).filter(
        TrainingRegistration.status == TrainingStatus.COMPLETED
    ).count()
    
    # Get total trainees
    total_trainees = db.query(Trainee).count()
    
    # Get registrations by status
    status_counts = db.query(
        TrainingRegistration.status, 
        func.count(TrainingRegistration.id)
    ).group_by(TrainingRegistration.status).all()
    
    # Format status counts as dict
    status_data = {status: count for status, count in status_counts}
    
    # Get recent registrations (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_registrations = db.query(TrainingRegistration).filter(
        TrainingRegistration.created_at >= thirty_days_ago
    ).count()
    
    return {
        "total_registrations": total_registrations,
        "completed_registrations": completed_registrations,
        "total_trainees": total_trainees,
        "status_breakdown": status_data,
        "recent_registrations": recent_registrations
    }

# Endpoint to get certificate counts by status
@app.get("/stats/counts")
async def get_certificate_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Check if user has admin privileges
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Total certificates
    total_count = db.query(CertificateDB).count()
    
    # Valid certificates (not revoked and not expired)
    valid_query = """
    SELECT COUNT(*) AS count FROM certificates
    WHERE is_revoked = FALSE
    AND (expiry_date IS NULL OR expiry_date > CURRENT_TIMESTAMP)
    """
    valid_result = db.execute(valid_query).fetchone()
    valid_count = valid_result.count if valid_result else 0
    
    # Expired certificates
    expired_query = """
    SELECT COUNT(*) AS count FROM certificates
    WHERE is_revoked = FALSE
    AND expiry_date IS NOT NULL AND expiry_date <= CURRENT_TIMESTAMP
    """
    expired_result = db.execute(expired_query).fetchone()
    expired_count = expired_result.count if expired_result else 0
    
    # Revoked certificates
    revoked_count = db.query(CertificateDB).filter(CertificateDB.is_revoked == True).count()
    
    # Certificates issued this month
    this_month_query = """
    SELECT COUNT(*) AS count FROM certificates
    WHERE DATE_TRUNC('month', issue_date) = DATE_TRUNC('month', CURRENT_TIMESTAMP)
    """
    this_month_result = db.execute(this_month_query).fetchone()
    this_month_count = this_month_result.count if this_month_result else 0
    
    return {
        "total": total_count,
        "valid": valid_count,
        "expired": expired_count,
        "revoked": revoked_count,
        "this_month": this_month_count
    }


async def generate_certificate(
    request: Request,
    background_tasks: BackgroundTasks,
    data: CertificateGenerationRequest,
    db: Session = None,
    current_user: User = None
):
    """
    Generate a new certificate for a trainee.
    """
    # Check if user is authenticated
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Validate trainee and registration
    trainee = db.query(Trainee).filter(Trainee.id == data.trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")
    
    registration = db.query(TrainingRegistration).filter(
        TrainingRegistration.id == data.training_registration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Training registration not found")
    
    # Check if certificate already exists
    existing_cert = db.query(CertificateDB).filter(
        CertificateDB.trainee_id == trainee.id,
        CertificateDB.registration_id == registration.id,
        CertificateDB.is_revoked == False
    ).first()
    
    if existing_cert:
        raise HTTPException(
            status_code=400,
            detail="A valid certificate already exists for this trainee and training registration"
        )
    
    # Generate unique certificate ID
    cert_id = generate_certificate_number(db, registration.registration_number, trainee.id)
    
    # Calculate expiry date if certification has validity days
    expiry_date = None
    if registration.training_certification_id:
        certification = db.query(TrainingCertification).filter(
            TrainingCertification.id == registration.training_certification_id
        ).first()
        
        if certification and certification.validity_days:
            base_date = trainee.training_completion_date or registration.training_date or datetime.now().date()
            expiry_date = base_date + timedelta(days=certification.validity_days)
    
    # Create certificate in database
    certificate = CertificateDB(
        id=cert_id,
        trainee_id=trainee.id,
        registration_id=registration.id,
        issue_date=datetime.now(),
        expiry_date=expiry_date,
        is_revoked=False
    )
    
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    
    # Get base URL for verification links
    base_url = str(request.base_url).rstrip('/')
    
    # Generate certificate image in the background
    background_tasks.add_task(
        generate_certificate_image,
        cert_id=cert_id,
        trainee_name=trainee.name,
        civil_id=trainee.civil_id,
        company_name=trainee.company_name,
        course_title=registration.training_course.title if registration.training_course else "Unnamed Course",
        training_date=registration.training_date,
        expiry_date=expiry_date,
        photo_path=trainee.photo_path,
        base_url=base_url,
        db=db
    )
    
    # Return certificate data
    return Certificate(
        id=certificate.id,
        trainee_id=certificate.trainee_id,
        registration_id=certificate.registration_id,
        issue_date=certificate.issue_date,
        expiry_date=certificate.expiry_date,
        is_revoked=certificate.is_revoked,
        revocation_reason=certificate.revocation_reason,
        certificate_path=certificate.certificate_path
    )
    
async def generate_certificate_route(
    request: Request,
    background_tasks: BackgroundTasks,
    data: CertificateGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Call your existing generate_certificate function
    return await generate_certificate(
        request, background_tasks, data, db, current_user
    )

@certificate_router.post("/generate", response_model=Certificate)
async def generate_certificate_route(
    request: Request,
    background_tasks: BackgroundTasks,
    data: CertificateGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return await generate_certificate(request, background_tasks, data, db, current_user)

async def list_certificates(
    trainee_id: Optional[int] = None,
    registration_id: Optional[int] = None,
    is_revoked: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = None,
    current_user: User = None
):
    """
    List certificates with optional filtering.
    """
    # Start with a query for all certificates
    query = db.query(CertificateDB)
    
    # Apply filters if provided
    if trainee_id is not None:
        query = query.filter(CertificateDB.trainee_id == trainee_id)
    
    if registration_id is not None:
        query = query.filter(CertificateDB.registration_id == registration_id)
    
    if is_revoked is not None:
        query = query.filter(CertificateDB.is_revoked == is_revoked)
    
    # Get results with pagination
    certificates = query.order_by(CertificateDB.issue_date.desc()).offset(skip).limit(limit).all()
    
    # Convert to response format
    result = []
    for cert in certificates:
        result.append(Certificate(
            id=cert.id,
            trainee_id=cert.trainee_id,
            registration_id=cert.registration_id,
            issue_date=cert.issue_date,
            expiry_date=cert.expiry_date,
            is_revoked=cert.is_revoked,
            revocation_reason=cert.revocation_reason,
            certificate_path=cert.certificate_path
        ))
    
    return result

async def verify_certificate(certificate_id: str, db: Session):
    """
    Verify a certificate by its ID.
    Returns verification details including validity status and certificate info.
    """
    # Find the certificate by ID
    certificate = db.query(CertificateDB).filter(CertificateDB.id == certificate_id).first()
    
    # If certificate doesn't exist
    if not certificate:
        return CertificateVerificationResponse(
            is_valid=False,
            error_message="Certificate not found"
        )
    
    # If certificate is revoked
    if certificate.is_revoked:
        return CertificateVerificationResponse(
            is_valid=False,
            error_message="Certificate has been revoked",
            trainee_name=certificate.trainee.name if certificate.trainee else None,
            trainee_id=certificate.trainee.civil_id if certificate.trainee else None,
            course_title=certificate.registration.training_course.title if certificate.registration and certificate.registration.training_course else None,
            registration_number=certificate.registration.registration_number if certificate.registration else None,
            training_date=format_date(certificate.registration.training_date) if certificate.registration else None,
            expiry_date=format_date(certificate.expiry_date) if certificate.expiry_date else None
        )
    
    # If certificate is expired
    if certificate.expiry_date and certificate.expiry_date < datetime.now():
        return CertificateVerificationResponse(
            is_valid=False,
            error_message="Certificate has expired",
            trainee_name=certificate.trainee.name if certificate.trainee else None,
            trainee_id=certificate.trainee.civil_id if certificate.trainee else None,
            company_name=certificate.trainee.company_name if certificate.trainee else None,
            course_title=certificate.registration.training_course.title if certificate.registration and certificate.registration.training_course else None,
            registration_number=certificate.registration.registration_number if certificate.registration else None,
            training_date=format_date(certificate.registration.training_date) if certificate.registration else None,
            expiry_date=format_date(certificate.expiry_date) if certificate.expiry_date else None
        )
    
    # If certificate is valid
    return CertificateVerificationResponse(
        is_valid=True,
        trainee_name=certificate.trainee.name if certificate.trainee else None,
        trainee_id=certificate.trainee.civil_id if certificate.trainee else None,
        company_name=certificate.trainee.company_name if certificate.trainee else None,
        course_title=certificate.registration.training_course.title if certificate.registration and certificate.registration.training_course else None,
        registration_number=certificate.registration.registration_number if certificate.registration else None,
        training_date=format_date(certificate.registration.training_date) if certificate.registration else None,
        expiry_date=format_date(certificate.expiry_date) if certificate.expiry_date else None
    )

@certificate_router.get("/", response_model=List[Certificate])
async def list_certificates_route(
    trainee_id: Optional[int] = None,
    registration_id: Optional[int] = None,
    is_revoked: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    return await list_certificates(trainee_id, registration_id, is_revoked, skip, limit, db, current_user)


@certificate_router.get("/verify/{certificate_id}", response_model=CertificateVerificationResponse)
async def verify_certificate_route(
    certificate_id: str, 
    db: Session = Depends(get_db)
):
    return await verify_certificate(certificate_id, db)

# Additional endpoints for certificate management
@certificate_router.get("/{certificate_id}", response_model=Certificate)
async def get_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    certificate = db.query(CertificateDB).filter(CertificateDB.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    return Certificate(
        id=certificate.id,
        trainee_id=certificate.trainee_id,
        registration_id=certificate.registration_id,
        issue_date=certificate.issue_date,
        expiry_date=certificate.expiry_date,
        is_revoked=certificate.is_revoked,
        revocation_reason=certificate.revocation_reason,
        certificate_path=certificate.certificate_path
    )

@certificate_router.put("/{certificate_id}/revoke", response_model=Certificate)
async def revoke_certificate(
    certificate_id: str,
    reason: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    certificate = db.query(CertificateDB).filter(CertificateDB.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    certificate.is_revoked = True
    certificate.revocation_reason = reason.get("reason")
    certificate.updated_at = datetime.now()
    
    db.commit()
    db.refresh(certificate)
    
    return Certificate(
        id=certificate.id,
        trainee_id=certificate.trainee_id,
        registration_id=certificate.registration_id,
        issue_date=certificate.issue_date,
        expiry_date=certificate.expiry_date,
        is_revoked=certificate.is_revoked,
        revocation_reason=certificate.revocation_reason,
        certificate_path=certificate.certificate_path
    )

@certificate_router.get("/{certificate_id}/download")
async def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    certificate = db.query(CertificateDB).filter(CertificateDB.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    if not certificate.certificate_path or not os.path.exists(certificate.certificate_path):
        raise HTTPException(status_code=404, detail="Certificate file not found")
    
    return FileResponse(
        certificate.certificate_path,
        filename=f"Certificate_{certificate_id}.pdf",
        media_type="application/pdf"
    )


# Include the router in your FastAPI app
app.include_router(certificate_router)

# Health Check Endpoint
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        # Perform a simple database query to check connectivity
        db.query(User).first()
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=f"Service unavailable: {str(e)}"
        )

# Version Endpoint
@app.get("/version")
async def get_version():
    return {
        "application_name": "Training Registration System",
        "version": "1.0.0",
        "description": "Comprehensive Training Management Platform"
    }

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": str(exc)
        }
    )

# Custom OpenAPI Schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Training Registration System",
        version="1.0.0",
        description="Comprehensive Training Management Platform for Tracking Registrations, Trainees, and Courses",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Run the application
if __name__ == "__main__":
    import uvicorn
   
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # Load environment variables for server configuration
    # HOST = os.getenv("APP_HOST", "0.0.0.0")
    # PORT = int(os.getenv("APP_PORT", 8000))
    # RELOAD = os.getenv("APP_RELOAD", "True").lower() == "true"
    
    # uvicorn.run(
    #     "main:app", 
    #     host=HOST, 
    #     port=PORT, 
    #     reload=RELOAD
    # )