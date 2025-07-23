import os
from datetime import datetime
import httpx
from fastapi import FastAPI, Query, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
import crud, models, schemas
from database import SessionLocal, async_engine

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not OPENWEATHER_API_KEY:
    raise RuntimeError("Не найден ключ OPENWEATHER_API_KEY в .env файле")

GEOCODING_API_URL = "http://api.openweathermap.org/geo/1.0/direct"
FORECAST_DAILY_API_URL = "https://api.openweathermap.org/data/2.5/forecast/daily"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://luggify.vercel.app", 
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Словарь переводов погодных условий
weather_translations = {
    # Гроза (2xx)
    "thunderstorm with light rain": "гроза с небольшим дождём",
    "thunderstorm with rain": "гроза с дождём",
    "thunderstorm with heavy rain": "гроза с сильным дождём",
    "light thunderstorm": "слабая гроза",
    "thunderstorm": "гроза",
    "heavy thunderstorm": "сильная гроза",
    "ragged thunderstorm": "рваная гроза",
    "thunderstorm with light drizzle": "гроза с лёгкой моросью",
    "thunderstorm with drizzle": "гроза с моросью",
    "thunderstorm with heavy drizzle": "гроза с сильной моросью",

    # Морось (3xx)
    "light intensity drizzle": "лёгкая морось",
    "drizzle": "морось",
    "heavy intensity drizzle": "сильная морось",
    "light intensity drizzle rain": "лёгкий дождь с моросью",
    "drizzle rain": "дождь с моросью",
    "heavy intensity drizzle rain": "сильный дождь с моросью",
    "shower rain and drizzle": "ливневый дождь с моросью",
    "heavy shower rain and drizzle": "сильный ливневый дождь с моросью",
    "shower drizzle": "ливневая морось",

    # Дождь (5xx)
    "light rain": "небольшой дождь",
    "moderate rain": "умеренный дождь",
    "heavy intensity rain": "сильный дождь",
    "very heavy rain": "очень сильный дождь",
    "extreme rain": "экстремальный дождь",
    "freezing rain": "ледяной дождь",
    "light intensity shower rain": "лёгкий ливневый дождь",
    "shower rain": "ливневый дождь",
    "heavy intensity shower rain": "сильный ливневый дождь",
    "ragged shower rain": "рваный ливень",

    # Снег (6xx)
    "light snow": "небольшой снег",
    "snow": "снег",
    "heavy snow": "сильный снег",
    "sleet": "дождь со снегом",
    "light shower sleet": "лёгкий дождь со снегом",
    "shower sleet": "ливень со снегом",
    "light rain and snow": "лёгкий дождь со снегом",
    "rain and snow": "дождь со снегом",
    "light shower snow": "лёгкий ливневый снег",
    "shower snow": "ливневый снег",
    "heavy shower snow": "сильный ливневый снег",

    # Атмосфера (7xx)
    "mist": "туман",
    "smoke": "дым",
    "haze": "дымка",
    "sand/dust whirls": "песок/пыль",
    "fog": "туман",
    "sand": "песок",
    "dust": "пыль",
    "volcanic ash": "вулканический пепел",
    "squalls": "шквалы",
    "tornado": "торнадо",

    # Ясно (800)
    "clear sky": "ясное небо",

    # Облака (80x)
    "few clouds": "малооблачно",
    "scattered clouds": "рассеянные облака",
    "broken clouds": "облачно с прояснениями",
    "overcast clouds": "пасмурно",
    "sky is clear": "чистое небо",
}

async def get_db():
    async with SessionLocal() as session:
        yield session

class PackingRequest(BaseModel):
    city: str
    start_date: str
    end_date: str

class DailyForecastItem(BaseModel):
    date: str
    temp_min: float
    temp_max: float
    condition: str
    icon: str

class ChecklistResponse(schemas.ChecklistOut):
    daily_forecast: list[DailyForecastItem]

@app.get("/geo/cities-autocomplete")
async def cities_autocomplete(namePrefix: str = Query(..., min_length=1)):
    params = {
        "q": namePrefix,
        "limit": 10,
        "appid": OPENWEATHER_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(GEOCODING_API_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    return [
        {
            "name": city["name"],
            "country": city["country"],
            "lat": city["lat"],
            "lon": city["lon"],
            "fullName": f"{city['name']}, {city['country']}"
        }
        for city in data
    ]

@app.post("/generate-packing-list", response_model=ChecklistResponse)
async def generate_list(req: PackingRequest, db: AsyncSession = Depends(get_db)):
    geocode_params = {
        "q": req.city,
        "limit": 1,
        "appid": OPENWEATHER_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        geo_resp = await client.get(GEOCODING_API_URL, params=geocode_params)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise HTTPException(status_code=404, detail="Город не найден")

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d")
        days_count = (end_dt - start_dt).days + 1

        if days_count > 16:
            raise HTTPException(status_code=400, detail="Период поездки не может превышать 16 дней")

        forecast_params = {
            "lat": lat,
            "lon": lon,
            "cnt": 16,
            "units": "metric",
            "appid": OPENWEATHER_API_KEY,
        }
        forecast_resp = await client.get(FORECAST_DAILY_API_URL, params=forecast_params)
        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()

    items = set()
    # Универсальные вещи
    items.update([
        "Паспорт",
        "Медицинская страховка",
        "Зарядка для телефона",
        "Телефон",
        "Деньги/карта",
        "Средства гигиены",
        "Одежда на каждый день",
        "Нижнее бельё",
        "Носки",
        "Зубная щётка и паста",
        "Дезодорант",
        "Личные лекарства",
        "Сумка/рюкзак",
        "Полотенце (если не предоставляется)",
        "Бутылка для воды",
        "Маска/антисептик",
    ])

    # Проверка визы (пример для стран Шенгена, США, Великобритании, Австралии)
    visa_countries = [
        "France", "Germany", "Italy", "Spain", "Greece", "Finland", "Sweden", "Norway", "Denmark",
        "Netherlands", "Belgium", "Austria", "Switzerland", "Czechia", "Poland", "Hungary", "USA",
        "United States", "United Kingdom", "UK", "Australia", "Canada", "Japan"
    ]
    # Получаем страну из geo_data
    country = geo_data[0].get("country", "")
    if country in visa_countries:
        items.add("Оформить визу")

    # Переходник для розеток (пример для Европы, США, Великобритании, Австралии)
    adapter_countries = [
        "USA", "United States", "United Kingdom", "UK", "Australia", "Japan", "China", "Switzerland"
    ]
    if country in adapter_countries:
        items.add("Переходник для розеток")

    # Длительная поездка (>7 дней)
    if days_count > 7:
        items.add("Средство для стирки одежды")

    # Температурные условия и осадки
    temps = []
    conditions = set()
    daily_forecast = []
    for day in forecast_data.get("list", []):
        forecast_date = datetime.fromtimestamp(day["dt"]).date()
        if start_dt.date() <= forecast_date <= end_dt.date():
            temp_day = day["temp"]["day"]
            temp_min = day["temp"]["min"]
            temp_max = day["temp"]["max"]
            weather = day["weather"][0]
            cond = weather["description"].lower()
            icon = weather["icon"]

            cond_ru = weather_translations.get(cond, cond)
            conditions.add(cond_ru)
            temps.append(temp_day)

            # Одежда по температуре
            if temp_day < 0:
                items.update(["Тёплая куртка/пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "Тёплые носки", "Зимние ботинки"])
            elif temp_day < 10:
                items.update(["Лёгкая куртка/ветровка", "Свитер/толстовка", "Джинсы/брюки", "Кроссовки/ботинки"])
            elif temp_day < 20:
                items.update(["Лёгкая кофта/свитшот", "Футболки", "Джинсы/брюки", "Кроссовки"])
            else:
                items.update(["Футболки", "Шорты/лёгкие платья", "Панама/кепка", "Солнцезащитные очки", "Легкая обувь"])

            # Осадки
            if "rain" in cond or "дождь" in cond_ru:
                items.add("Зонт или дождевик")
                items.add("Водонепроницаемая обувь")
            if "snow" in cond or "снег" in cond_ru:
                items.add("Тёплая обувь")
            if "sun" in cond or temp_day > 20:
                items.add("Солнцезащитный крем")

            daily_forecast.append(DailyForecastItem(
                date=str(forecast_date),
                temp_min=temp_min,
                temp_max=temp_max,
                condition=cond_ru,
                icon=icon
            ))

    avg_temp = round(sum(temps) / len(temps), 1) if temps else None

    # Особые случаи
    if any("swim" in c or "купание" in c for c in conditions) or country in ["TH", "ES", "GR", "IT", "TR", "EG"]:
        items.add("Купальник")
    if any("mountain" in c or "гора" in c for c in conditions):
        items.update(["Треккинговая обувь", "Аптечка", "Термос", "Карта/компас"])

    # --- Категории и условия ---
    categories = {
        "Важное": [],
        "Документы": [],
        "Одежда": [],
        "Гигиена": [],
        "Техника": [],
        "Аптечка": [],
        "Прочее": []
    }

    # Важное
    categories["Важное"].append("Паспорт")
    categories["Важное"].append("Медицинская страховка")
    categories["Важное"].append("Деньги/карта")
    # Список стран с визовым режимом (ISO Alpha-2)
    visa_countries = [
        # Европа (Шенген)
        "FR", "DE", "IT", "ES", "GR", "FI", "SE", "NO", "DK",
        "NL", "BE", "AT", "CH", "CZ", "PL", "HU", "PT",
        "SK", "SI", "EE", "LV", "LT", "IS", "LU", "MT",
        # Великобритания
        "GB",
        # США, Канада
        "US", "CA",
        # Азия
        "JP", "CN", "IN", "VN", "KR", "SG", "MY", "PH", "ID",
        # Ближний Восток
        "IL", "AE", "QA", "SA", "KW", "OM", "BH",
        # Африка
        "EG", "MA", "TN", "DZ", "ZA",
        # Австралия, Океания
        "AU", "NZ",
        # Америка
        "MX", "BR", "AR", "CL", "CO", "PE", "CU", "DO",
        # Прочие
        "TR"
    ]
    country = geo_data[0].get("country", "")
    if country in visa_countries:
        categories["Важное"].append("Виза")

    # Документы
    categories["Документы"].append("Билеты")
    categories["Документы"].append("Бронь отеля")
    # Водительское удостоверение — если страна не Россия
    if country and country != "RU":
        categories["Документы"].append("Водительское удостоверение")

    # Одежда (по погоде)
    min_temp = min(temps) if temps else 15
    max_temp = max(temps) if temps else 20
    if min_temp < 0:
        categories["Одежда"].extend(["Тёплая куртка", "Шапка", "Шарф", "Перчатки", "Термобельё", "Зимние ботинки", "Тёплые носки"])
    elif min_temp < 10:
        categories["Одежда"].extend(["Лёгкая куртка", "Свитер", "Джинсы", "Кроссовки"])
    elif max_temp > 20:
        categories["Одежда"].extend(["Футболки", "Шорты", "Панама", "Легкая обувь"])
    else:
        categories["Одежда"].extend(["Футболки", "Джинсы", "Кроссовки"])
    # Дождь
    if any("rain" in c or "дождь" in c for c in conditions):
        categories["Одежда"].append("Дождевик")
        categories["Одежда"].append("Водонепроницаемая обувь")
    # Солнце/жара
    if max_temp > 22:
        categories["Одежда"].append("Солнцезащитные очки")
        categories["Одежда"].append("Панама")
    # Купальник
    if any("swim" in c or "купание" in c for c in conditions) or country in ["TH", "ES", "GR", "IT", "TR", "EG"]:
        categories["Одежда"].append("Купальник")
    # Горы
    if any("mountain" in c or "гора" in c for c in conditions):
        categories["Одежда"].append("Треккинговая обувь")

    # Гигиена
    categories["Гигиена"].extend(["Зубная щётка", "Паста", "Дезодорант", "Мыло", "Расчёска"])

    # Техника
    categories["Техника"].extend(["Телефон", "Зарядка", "Пауэрбанк"])
    # Переходник для розеток
    adapter_countries = [
        "USA", "United States", "United Kingdom", "UK", "Australia", "Japan", "China", "Switzerland"
    ]
    if country in adapter_countries:
        categories["Техника"].append("Переходник для розеток")

    # Аптечка
    categories["Аптечка"].extend(["Личные лекарства", "Пластыри", "Обезболивающее"])

    # Прочее
    if max_temp > 20:
        categories["Прочее"].append("Бутылка для воды")
    if any("rain" in c or "дождь" in c for c in conditions):
        categories["Прочее"].append("Зонт")
    # Убираем дубли
    for k in categories:
        categories[k] = list(dict.fromkeys(categories[k]))
    # Собираем все вещи в один список для сохранения
    all_items = []
    for v in categories.values():
        all_items.extend(v)
    # Добавляем 'Виза' в итоговый список, если страна визовая и если её ещё нет
    if country in visa_countries and "Виза" not in all_items:
        all_items.append("Виза")

    checklist_data = schemas.ChecklistCreate(
        city=req.city,
        start_date=start_dt.date(),
        end_date=end_dt.date(),
        items=all_items,
        avg_temp=avg_temp,
        conditions=sorted(conditions),
        daily_forecast=daily_forecast
    )

    checklist = await crud.create_checklist(db, checklist_data)

    return {
        "slug": checklist.slug,
        "city": checklist.city,
        "start_date": checklist.start_date,
        "end_date": checklist.end_date,
        "items": all_items,
        "items_by_category": categories,
        "avg_temp": checklist.avg_temp,
        "conditions": checklist.conditions,
        "daily_forecast": daily_forecast
    }

@app.get("/checklist/{slug}", response_model=schemas.ChecklistOut)
async def get_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    # Категории для чеклиста (для фронта)
    categories = {
        "Важное": [],
        "Документы": [],
        "Одежда": [],
        "Гигиена": [],
        "Техника": [],
        "Аптечка": [],
        "Прочее": []
    }
    for item in checklist.items:
        for k in categories:
            if item in categories[k]:
                break
        # Важное
        if item in ["Паспорт", "Медицинская страховка", "Деньги/карта", "Виза"]:
            categories["Важное"].append(item)
        # Документы
        elif item in ["Билеты", "Бронь отеля", "Водительское удостоверение"]:
            categories["Документы"].append(item)
        # Одежда
        elif item in ["Тёплая куртка", "Шапка", "Шарф", "Перчатки", "Термобельё", "Зимние ботинки", "Тёплые носки", "Лёгкая куртка", "Свитер", "Джинсы", "Кроссовки", "Футболки", "Шорты", "Панама", "Легкая обувь", "Купальник", "Треккинговая обувь", "Зонт/дождевик", "Водонепроницаемая обувь", "Солнцезащитные очки"]:
            categories["Одежда"].append(item)
        # Гигиена
        elif item in ["Зубная щётка", "Паста", "Дезодорант", "Мыло", "Расчёска"]:
            categories["Гигиена"].append(item)
        # Техника
        elif item in ["Телефон", "Зарядка", "Пауэрбанк", "Переходник для розеток"]:
            categories["Техника"].append(item)
        # Аптечка
        elif item in ["Личные лекарства", "Пластыри", "Обезболивающее"]:
            categories["Аптечка"].append(item)
        # Прочее
        elif item in ["Бутылка для воды", "Термос"]:
            categories["Прочее"].append(item)
    # Убираем дубли
    for k in categories:
        categories[k] = list(dict.fromkeys(categories[k]))

    return {
        "slug": checklist.slug,
        "city": checklist.city,
        "start_date": checklist.start_date,
        "end_date": checklist.end_date,
        "items": checklist.items,
        "items_by_category": categories,
        "avg_temp": checklist.avg_temp,
        "conditions": checklist.conditions,
    }

@app.get("/")
async def root():
    return {"message": "Luggify backend is running"}
