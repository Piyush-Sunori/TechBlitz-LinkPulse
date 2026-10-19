"""
LinkPulse Database Reset & Fresh Start Script
Wipes all existing database tables and re-initializes a clean schema.
Usage: python reset_db.py
"""

import logging

from app.database import engine, Base
from app.models import User, Campaign, Link, Click, DomainBlocklist

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reset_db")

def reset_database():
    logger.warning("WIPING ENTIRE LINKPULSE DATABASE")
    
    # Drop all existing tables
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ All tables dropped successfully.")
    except Exception:
        logger.exception("Error dropping tables")
        raise
        
    # Re-create fresh clean schema
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("🎉 Clean database schema created successfully!")
        logger.info("Ready for a fresh start.")
    except Exception:
        logger.exception("Error creating schema")
        raise

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete ALL data and reset the database? (y/N): ")
    if confirm.strip().lower() == "y":
        reset_database()
    else:
        print("Database reset cancelled.")
