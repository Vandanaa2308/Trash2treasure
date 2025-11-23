# migrate_fix.py
from app import app
from extensions import db
import sqlalchemy

with app.app_context():
    engine = db.get_engine()
    conn = engine.connect()
    print("DB engine:", engine)

    try:
        # Try adding is_sold column (SQLite/Postgres/MySQL all support ADD COLUMN)
        conn.execute(sqlalchemy.text("ALTER TABLE item ADD COLUMN is_sold BOOLEAN DEFAULT 0"))
        print("ALTER TABLE executed (attempted to add is_sold).")
    except Exception as e:
        print("ALTER TABLE failed or column may already exist:", e)

    # Create any missing tables that are defined in models (safe: only creates tables that don't exist)
    db.create_all()
    print("db.create_all() finished. Missing tables (if any) should be created.")
    conn.close()
