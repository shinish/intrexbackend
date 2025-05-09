#!/bin/bash
# PostgreSQL setup script for Training Registration System

# Create the database
psql -U postgres -c "CREATE DATABASE training_system;"

# Connect to the database and create extensions if needed
psql -U postgres -d training_system -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"

echo "PostgreSQL database 'training_system' has been created."
echo "Database connection details:"
echo "  - Host: localhost"
echo "  - Database: training_system"
echo "  - Username: postgres"
echo "  - Password: 123456"
echo ""
echo "To run the application, use: uvicorn main:app --reload"