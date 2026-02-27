from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base
 
class User(Base):
    __tablename__ = 'users'
 
    id          = Column(Integer, primary_key=True, index=True)
    roll_number = Column(String, unique=True, index=True, nullable=False)
    name        = Column(String, nullable=False)
    role        = Column(String, default='student')  # student/driver/coordinator
    is_fee_paid = Column(Boolean, default=False)
    password_hash = Column(String, nullable=False)
