# backend/database.py
"""
Database instance module.
Separating the db instance from app.py prevents circular import issues.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

