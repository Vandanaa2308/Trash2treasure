# create_tables.py
from app import app
from extensions import db 
import models

if __name__=="__main__":
    with app.app_context():
        db.create_all()
        print("All tables created successfully.")
