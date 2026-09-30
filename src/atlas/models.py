"""Operational metadata. Analytical events live in the warehouse."""
import os
from sqlalchemy import create_engine, String, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default='viewer')

def engine():
    return create_engine(os.getenv('ATLAS_DATABASE_URL', 'sqlite:///data/app.db'), pool_pre_ping=True)

def session():
    with sessionmaker(bind=engine())() as db:
        yield db
