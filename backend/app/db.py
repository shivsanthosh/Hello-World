import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATA_DIR = os.environ.get("PANEL_STUDIO_DATA", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
os.makedirs(os.path.join(DATA_DIR, "reports"), exist_ok=True)
DB_URL = os.environ.get("PANEL_STUDIO_DB", f"sqlite:///{os.path.join(DATA_DIR, 'panel_studio.db')}")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
