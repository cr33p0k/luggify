from sqlalchemy import Column, Integer, String, Date, Float, Text
from sqlalchemy.dialects.postgresql import ARRAY
from server.database import Base

class Checklist(Base):
    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    items = Column(ARRAY(String))  # массив строк
    avg_temp = Column(Float)        # float вместо строки
    conditions = Column(ARRAY(String))
    slug = Column(String, unique=True, index=True)  # токен/slug
