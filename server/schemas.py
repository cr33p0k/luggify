from typing import Optional, List
from pydantic import BaseModel
from datetime import date

class DailyForecast(BaseModel):
    date: date
    condition: str
    icon: str
    temp_min: float
    temp_max: float

class ChecklistCreate(BaseModel):
    city: str
    start_date: date
    end_date: date
    items: List[str]
    avg_temp: float
    conditions: List[str]

class ChecklistOut(ChecklistCreate):
    slug: str
