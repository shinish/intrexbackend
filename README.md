# Training Registration System

A comprehensive FastAPI application for managing training registrations, certifications, customers, trainers, and course information.

## Features

- User authentication with JWT tokens
- Complete CRUD operations for all entities
- Training registration workflow
- Training confirmation process
- Role-based access control (Admin/Regular users)

## Database Entities

- **User**: System users with authentication
- **Customer**: Organizations requesting training
- **Trainer**: Freelancers or employees who conduct training
- **Training Course**: Available courses 
- **Training Certification**: Certification programs
- **Training Registration**: Main entity tracking training requests and confirmations

## API Endpoints

### Authentication
- POST `/token`: Get access token

### User Management
- POST `/users/`: Create new user (admin only)
- GET `/users/me/`: Get current user details

### Customers
- POST `/customers/`: Create customer
- GET `/customers/`: List all customers
- GET `/customers/{customer_id}`: Get customer details

### Training Courses
- POST `/training-courses/`: Create training course
- GET `/training-courses/`: List all training courses
- GET `/training-courses/{course_id}`: Get course details

### Trainers
- POST `/trainers/`: Create trainer
- GET `/trainers/`: List all trainers
- GET `/trainers/{trainer_id}`: Get trainer details

### Training Certifications
- POST `/training-certifications/`: Create certification
- GET `/training-certifications/`: List all certifications
- GET `/training-certifications/{certification_id}`: Get certification details

### Training Registrations
- POST `/training-registrations/`: Create training registration
- GET `/training-registrations/`: List all registrations
- GET `/training-registrations/{registration_id}`: Get registration details
- PUT `/training-registrations/{registration_id}/status`: Update training status

### Training Confirmations
- POST `/training-confirmations/`: Confirm a training registration

## Schema Details

### Training Registration
- Registration Number (auto-generated)
- Request Date
- Request Receiver
- Customer (linked to Customers table)
- Customer Point of Contact
- Training Course (linked to Training Courses table)
- Number of Trainees
- Unit Rate (KD)
- Total Amount (KD)
- Payment Type (Cash/Credit)
- Trainer (linked to Trainers table)
- Training Date
- Training & Certification (linked to Training Certifications table)
- Status (Pending/Confirmed/Completed/Cancelled)
- Remarks

### Training Confirmation
- Training Registration Reference 
- Training Date
- Training Time
- Trainer
- Customer Name
- Training Course
- Number of Trainees
- Unit Rate (KD)
- Total Amount (KD)
- Training Venue
- Training Status
- Remarks

## Setup and Installation

1. Clone the repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   uvicorn main:app --reload
   ```
4. Access the API documentation at `http://localhost:8000/docs`

## Default User Credentials

The application automatically creates the following default users on startup:

1. **Admin User**
   - Username: admin
   - Password: adminpassword
   - Has full access to all features

2. **Regular User**
   - Username: user
   - Password: userpassword
   - Has access to standard operations

*Note: It's highly recommended to change these credentials in production*

## Database

The application uses PostgreSQL with the following configuration:
- Host: localhost
- Database: training_system
- Username: postgres
- Password: 123456

### Database Setup:

1. Make sure PostgreSQL is installed on your system
2. Create the database:
   ```
   psql -U postgres -c "CREATE DATABASE training_system;"
   ```
3. The application will automatically create all required tables on startup

You can also run the provided setup script:
```
chmod +x postgres_setup.sh
./postgres_setup.sh
```