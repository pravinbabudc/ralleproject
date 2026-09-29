import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hybridflowguard.db")

# connect_args={"check_same_thread": False} is required for SQLite in multithreaded environment
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def run_migrations():
    from sqlalchemy import inspect, text
    try:
        with engine.connect() as conn:
            insp = inspect(conn)
            tables = insp.get_table_names()
            if "flow_records" in tables:
                cols = [c["name"] for c in insp.get_columns("flow_records")]
                if "jitter_ms" not in cols:
                    conn.execute(text("ALTER TABLE flow_records ADD COLUMN jitter_ms FLOAT DEFAULT 1.0"))
                if "burst_factor" not in cols:
                    conn.execute(text("ALTER TABLE flow_records ADD COLUMN burst_factor FLOAT DEFAULT 1.0"))
                conn.commit()
    except Exception:
        pass

run_migrations()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
