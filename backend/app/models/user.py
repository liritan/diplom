from app.db.base import Base
from sqlalchemy import Column, Integer, String, Boolean, Enum as PgEnum
import enum

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(PgEnum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
