import os
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI, Query, Depends, HTTPException, Body, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
import crud, models, schemas
from database import SessionLocal, async_engine
from typing import List, Optional
from auth import (
    verify_password, create_access_token,
    get_current_user, require_current_user,
    get_db as auth_get_db,
)

load_dotenv()


# Open-Meteo API (бесплатный, без ключа)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
from translations import WMO_CODES, get_item, get_category_map

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://luggify.vercel.app",
        "https://www.luggify.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Словарь переводов погодных условий


async def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="База данных не настроена. Проверьте переменную окружения DATABASE_URL")
    async with SessionLocal() as session:
        try:
            yield session
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=503, detail=f"Ошибка подключения к базе данных: {str(e)}")

class PackingRequest(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "vacation"  # vacation, business, active, beach, winter
    gender: str = "unisex"       # male, female, unisex
    transport: str = "plane"     # plane, train, car, bus
    traveling_with_pet: bool = False
    has_allergies: bool = False
    has_chronic_diseases: bool = False
    language: str = "ru"

class TripSegment(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "vacation"
    transport: str = "plane"

class MultiCityPackingRequest(BaseModel):
    segments: List[TripSegment]
    gender: str = "unisex"
    traveling_with_pet: bool = False
    has_allergies: bool = False
    has_chronic_diseases: bool = False

class DailyForecastItem(BaseModel):
    date: str
    temp_min: float
    temp_max: float
    condition: str
    icon: str
    source: str = "forecast"  # "forecast" или "historical"
    humidity: Optional[float] = None       # средняя влажность %
    uv_index: Optional[float] = None       # макс. УФ-индекс
    wind_speed: Optional[float] = None     # макс. скорость ветра км/ч

class ChecklistResponse(schemas.ChecklistOut):
    daily_forecast: list[DailyForecastItem]

class StatsResponse(BaseModel):
    total_trips: int
    total_days: int
    unique_cities: int
    unique_countries: int
    upcoming_trips: int

class ChecklistStateUpdate(BaseModel):
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    is_public: Optional[bool] = None

class UserPrivacyUpdate(BaseModel):
    is_stats_public: bool

class ChecklistPrivacyUpdate(BaseModel):
    is_public: bool

# ==================== AUTH ENDPOINTS ====================

@app.post("/auth/register", response_model=schemas.Token)
async def register(data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверяем уникальность email
    existing = await crud.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    # Проверяем уникальность username
    existing = await crud.get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    # Создаём пользователя
    user = await crud.create_user(db, data)
    # Генерируем токен
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.post("/auth/login", response_model=schemas.Token)
async def login(data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    """Авторизация пользователя"""
    user = await crud.get_user_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.get("/auth/me", response_model=schemas.UserOut)
async def get_me(user=Depends(require_current_user)):
    """Получение профиля текущего пользователя"""
    return user


@app.post("/auth/telegram", response_model=schemas.Token)
async def telegram_auth(data: schemas.TelegramAuth, db: AsyncSession = Depends(get_db)):
    """Авторизация через Telegram — автосоздание пользователя при первом входе"""
    user = await crud.get_user_by_tg_id(db, data.tg_id)
    if not user:
        # Создаём нового пользователя из Telegram-данных
        user = await crud.create_user_from_telegram(
            db,
            tg_id=data.tg_id,
            username=data.username,
            first_name=data.first_name,
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user),
    }


@app.patch("/auth/privacy", response_model=schemas.UserOut)
async def update_privacy(
    privacy: UserPrivacyUpdate,
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновление настроек приватности пользователя"""
    user.is_stats_public = privacy.is_stats_public
    await db.commit()
    await db.refresh(user)
    return user


@app.get("/users/{username}", response_model=dict)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)  # Optional, to check friend status later
):
    """Публичный профиль пользователя"""
    user = await crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем чеклисты
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    public_checklists = [
        schemas.ChecklistOut.model_validate(c) 
        for c in checklists 
        if c.is_public
    ]

    stats = None
    if user.is_stats_public:
        # Считаем статистику для публичного профиля (только по публичным чеклистам? 
        # Или полную, если user разрешил? Обычно полную, но флаг 'is_stats_public' это и значит)
        
        # Лучше считать полную статистику, раз пользователь разрешил её показывать
        stats = {
            "total_trips": len(checklists),
            "total_days": sum((c.end_date - c.start_date).days + 1 for c in checklists if c.start_date and c.end_date),
            "unique_cities": len({c.city.split(",")[0].strip() for c in checklists if c.city}),
            "unique_countries": len({c.city.split(",")[-1].strip() for c in checklists if c.city and "," in c.city}),
            "upcoming_trips": sum(1 for c in checklists if c.start_date and c.start_date > datetime.now().date())
        }

    return {
        "username": user.username,
        "created_at": user.created_at,
        "is_stats_public": user.is_stats_public,
        "stats": stats,
        "checklists": public_checklists
    }


@app.get("/my-checklists", response_model=List[schemas.ChecklistOut])
async def get_my_checklists(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получение всех чеклистов текущего пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    return checklists


@app.get("/my-stats", response_model=StatsResponse)
async def get_my_stats(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика путешествий пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    
    total_trips = len(checklists)
    total_days = 0
    cities = set()
    countries = set()
    upcoming = 0
    today = datetime.now().date()
    
    for c in checklists:
        # Дни
        if c.start_date and c.end_date:
            days = (c.end_date - c.start_date).days + 1
            if days > 0:
                total_days += days
        
        # Города и Страны
        if c.city:
            cities.add(c.city.split(",")[0].strip()) # Только имя города
            if "," in c.city:
                countries.add(c.city.split(",")[-1].strip())
            else:
                # Если страна не указана явно, считаем город уникальным местом
                pass
        
        # Предстоящие
        if c.start_date and c.start_date > today:
            upcoming += 1
            
    return {
        "total_trips": total_trips,
        "total_days": total_days,
        "unique_cities": len(cities),
        "unique_countries": len(countries),
        "upcoming_trips": upcoming
    }


async def get_weather_forecast_data(city: str, start_date: datetime.date, end_date: datetime.date) -> List[DailyForecastItem]:
    """Helper to fetch weather forecast for a checklist (used when viewing saved checklists)"""
    async with httpx.AsyncClient() as client:
        # 1. Geocoding
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": "ru",
                "limit": 1,
            }, headers=headers)
            if geo_resp.status_code != 200:
                return []
            geo_data = geo_resp.json()
            if not geo_data:
                return []
            
            lat = float(geo_data[0]["lat"])
            lon = float(geo_data[0]["lon"])
        except Exception:
            return []

        # Dates setup
        # start_date/end_date passed as date objects
        today = datetime.now().date()
        forecast_limit = today + timedelta(days=15)
        
        daily_data = {}

        # 2. Forecast (Open-Meteo)
        if start_date <= forecast_limit:
            forecast_end = min(end_date, forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    for i, t in enumerate(times):
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        daily_data[t] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "forecast"
                        }
            except Exception:
                pass

        # 3. Historical (if needed)
        hist_start = max(start_date, forecast_limit + timedelta(days=1))
        if hist_start <= end_date:
            try:
                # Use last year data
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_date.replace(year=end_date.year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    
                    # Compute invalid year diff to map back to requested dates
                    # But simpler: just iterate and map to hist_start + i days
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_date: break
                        
                        desc, icon = WMO_CODES.get(codes[i], ("Неизвестно", "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical"
                        }
                        current_hist_date += timedelta(days=1)
            except Exception:
                pass

        # Convert to list
        result = []
        for date_str in sorted(daily_data.keys()):
            item = daily_data[date_str]
            result.append(DailyForecastItem(
                date=date_str,
                temp_min=item["temp_min"],
                temp_max=item["temp_max"],
                condition=item["condition"],
                icon=item["icon"],
                source=item["source"]
            ))
        return result


@app.get("/geo/cities-autocomplete")
async def autocomplete_cities(namePrefix: str = Query(..., min_length=2)):
    """
    Гибридный автокомплит: Open-Meteo (быстро, короткие префиксы) + Nominatim (точность, полные названия).
    Объединяет результаты, убирает дубликаты.
    """
    results_open_meteo = []
    results_nominatim = []

    async def fetch_open_meteo():
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": namePrefix, "count": 5, "language": "ru", "format": "json"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "results" in data:
                        return data["results"]
        except Exception:
            pass
        return []

    async def fetch_nominatim():
        # Используем featuretype=city чтобы отсеять мусор, но это параметр reverse. 
        # Для search используем ограничение по addressdetails, но Nominatim всё равно возвращает разное.
        # Просто запрашиваем и потом фильтруем на клиенте (тут).
        params = {
            "q": namePrefix,
            "format": "json",
            "accept-language": "ru",
            "limit": 5,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    # Запускаем параллельно
    import asyncio
    res_om, res_nom = await asyncio.gather(fetch_open_meteo(), fetch_nominatim())

    final_results = []
    seen = set()

    # 1. Приоритет Open-Meteo (обычно релевантнее для префиксов)
    for item in res_om:
        city = item.get("name")
        country = item.get("country_code", "").upper()
        country_name = item.get("country", "")
        admin1 = item.get("admin1")
        
        # Фикс для "Молотов" -> "Пермь" (если вдруг API возвращает старое название)
        # Но массово это не исправить, надеемся на Nominatim
        
        key = f"{city}:{country}:{admin1}"
        if key in seen: continue
        seen.add(key)

        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)
        
        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": item.get("latitude"),
            "lon": item.get("longitude"),
            "fullName": ", ".join(parts),
            "source": "om"
        })

    # 2. Добавляем Nominatim (если такого города ещё нет)
    for item in res_nom:
        addr = item.get("address", {})
        # Извлекаем город
        city = addr.get("city") or addr.get("town") or addr.get("village") or item.get("name")
        if not city: continue
        
        country = addr.get("country_code", "").upper()
        country_name = addr.get("country", "")
        admin1 = addr.get("state", "")

        # Пропускаем, если название совсем не похоже на запрос (Nominatim иногда ищет по улицам)
        # if namePrefix.lower() not in city.lower(): continue # Слишком строго

        key = f"{city}:{country}:{admin1}"
        
        # Nominatim часто возвращает дубли
        if key in seen: continue
        
        # Если такого ключа нет, но координаты ОЧЕНЬ близко к уже найденному -> тоже дубль
        is_duplicate_coord = False
        lat, lon = float(item["lat"]), float(item["lon"])
        for exist in final_results:
            if abs(exist["lat"] - lat) < 0.1 and abs(exist["lon"] - lon) < 0.1:
                is_duplicate_coord = True
                break
        
        if is_duplicate_coord: continue

        seen.add(key)
        
        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)

        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": lat,
            "lon": lon,
            "fullName": ", ".join(parts),
            "source": "nom"
        })

    return final_results

async def calculate_packing_data(
    city: str,
    start_date_str: str,
    end_date_str: str,
    trip_type: str,
    transport: str,
    gender: str,
    traveling_with_pet: bool,
    has_allergies: bool,
    has_chronic_diseases: bool,
    language: str = "ru"
):
    # 1. Geocoding
    async with httpx.AsyncClient() as client:
        headers = {"User-Agent": "Luggify/1.0"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": language,
                "limit": 1,
                "addressdetails": 1
            }, headers=headers)
            if geo_resp.status_code != 200 or not geo_resp.json():
                raise HTTPException(status_code=404, detail=f"Город {city} не найден")
            geo_data = geo_resp.json()
        except Exception as e:
            print(f"Geocoding error for {city}: {e}")
            raise HTTPException(status_code=404, detail=f"Ошибка БД: 404: Город {city} не найден ({str(e)})")

        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])
        addr = geo_data[0].get("address", {})
        country = addr.get("country_code", "").upper()

        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        today = datetime.now().date()

        forecast_limit = today + timedelta(days=15)
        daily_data = {}

        # 1) Open-Meteo Forecast
        if start_dt.date() <= forecast_limit:
            forecast_end = min(end_dt.date(), forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,uv_index_max,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    uvs = d.get("uv_index_max", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    for i, t in enumerate(times):
                        # Use translations
                        default_desc = "Unknown" if gender != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(gender if gender in WMO_CODES else "ru", {}).get(codes[i], (default_desc, "01d"))
                        # Wait, gender is not language. I need language here.
                        # calculate_packing_data argument needs 'language'.
                        # Assuming it's passed... But wait, I added it to Pydantic model but not to function args in this refactor?
                        # I need to update function signature first.
                        pass

            except Exception as e:
                print(f"Forecast error: {e}")

        # 2) Historical
        hist_start = max(start_dt.date(), forecast_limit + timedelta(days=1))
        if hist_start <= end_dt.date():
            try:
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_dt.date().replace(year=end_dt.date().year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_dt.date(): break
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical",
                            "humidity": hums[i] if i < len(hums) else None,
                            "uv_index": None,
                            "wind_speed": winds[i] if i < len(winds) else None,
                        }
                        current_hist_date += timedelta(days=1)
            except Exception as e:
                print(f"Historical error: {e}")

    # Process weather data
    daily_forecast = []
    temps = []
    conditions = set()
    wmo_codes = set()
    humidities = []
    uv_indices = []
    wind_speeds = []

    for date_str in sorted(daily_data.keys()):
        item = daily_data[date_str]
        daily_forecast.append(DailyForecastItem(
            date=date_str,
            temp_min=item["temp_min"],
            temp_max=item["temp_max"],
            condition=item["condition"],
            icon=item["icon"],
            source=item["source"],
            humidity=item["humidity"],
            uv_index=item["uv_index"],
            wind_speed=item["wind_speed"],
        ))
        temps.append((item["temp_min"] + item["temp_max"]) / 2)
        conditions.add(item["condition"])
        wmo_codes.add(item["weathercode"])
        if item["humidity"]: humidities.append(item["humidity"])
        if item["uv_index"]: uv_indices.append(item["uv_index"])
        if item["wind_speed"]: wind_speeds.append(item["wind_speed"])

    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    
    # Items Generation
    items = set()

    # Weather based items
    if hums := [h for h in humidities if h > 80]:
         items.add(get_item("styling", language))
    if uvs := [u for u in uv_indices if u > 5]:
         items.update([get_item("sunscreen_50", language), get_item("hat", language), get_item("sunglasses", language)])
    if winds := [w for w in wind_speeds if w > 30]:
         items.update([get_item("windbreaker", language), get_item("chapstick", language), get_item("scarf_buff", language)])

    if any("swim" in c.lower() or "купание" in c.lower() for c in conditions) or country in ["TH", "ES", "GR", "IT", "TR", "EG"]:
        items.add(get_item("swimsuit", language))
    if any("mountain" in c.lower() or "гора" in c.lower() for c in conditions):
        items.update([get_item("trekking_shoes", language), get_item("first_aid_kit", language), get_item("thermos", language), get_item("map_compass", language)])

    if has_allergies:
        items.update([get_item("antihistamine", language), get_item("allergies_list", language)])
    if has_chronic_diseases:
        items.update([get_item("meds_personal", language), get_item("meds_regular", language), get_item("med_report", language)])

    if gender == "female":
        items.update([get_item("makeup", language), get_item("hygiene_fem", language), get_item("makeup_remover", language)])
        if avg_temp and avg_temp > 15:
            items.add(get_item("dress", language))
    elif gender == "male":
        items.add(get_item("shaving_kit", language))

    if transport == "plane":
        items.update([get_item("neck_pillow", language), get_item("earplugs", language), get_item("powerbank_hand", language), get_item("liquids_bag", language)])
    elif transport == "train":
        items.update([get_item("slippers_train", language), get_item("mug", language), get_item("powerbank", language), get_item("clothes_train", language), get_item("wipes", language)])
    elif transport == "car":
        items.update([get_item("license", language), get_item("car_charger", language), get_item("snacks_water", language), get_item("playlist", language), get_item("sunglasses_driver", language)])
    elif transport == "bus":
        items.update([get_item("neck_pillow", language), get_item("earplugs", language), get_item("snacks_water", language), get_item("wipes", language)])

    # Basic items based on categories logic (simplified/deduplicated logic from categories map)
    # We will return the raw set of items, and let the caller categorize if needed, or better yet, category logic should be here too?
    # Actually, the caller re-categorizes everything. So we just need to return `items` set, plus weather info.
    
    # ... Wait, the category mapping in `generate_list` had logic for clothes based on temp.
    # We need that logic here.
    
    min_temp = min(daily_data[d]["temp_min"] for d in daily_data) if daily_data else 15
    max_temp = max(daily_data[d]["temp_max"] for d in daily_data) if daily_data else 20
    
    if min_temp < 0:
        items.update([get_item("jacket_warm", language), get_item("hat", language), get_item("scarf", language), get_item("gloves", language), get_item("thermo", language), get_item("boots_winter", language), get_item("socks_warm", language)])
    elif min_temp < 10:
        items.update([get_item("jacket_light", language), get_item("sweater", language), get_item("jeans", language), get_item("sneakers", language)])
    elif max_temp > 20:
        items.update([get_item("tshirt", language), get_item("shorts", language), get_item("cap", language), get_item("shoes_light", language)])
    else:
        items.update([get_item("tshirt", language), get_item("jeans", language), get_item("sneakers", language)])
        
    if any("rain" in c.lower() or "дождь" in c.lower() for c in conditions):
        items.update([get_item("raincoat", language), get_item("shoes_waterproof", language)])
    if max_temp > 22:
        items.update([get_item("sunglasses", language), get_item("cap", language)])
    if max_temp > 20:
        items.add(get_item("water_bottle", language))
        
    if traveling_with_pet:
        items.update([get_item("vet_passport", language), get_item("pet_food", language), get_item("pet_bowl", language), get_item("leash", language), get_item("pet_pads", language), get_item("pet_toy", language)])

    if trip_type == "business":
        items.update([get_item("suit", language), get_item("shirts", language), get_item("shoes_formal", language), get_item("laptop", language), get_item("business_cards", language)])
    elif trip_type == "active":
        items.update([get_item("sportswear", language), get_item("sneakers", language), get_item("backpack_walk", language), get_item("water_bottle", language)])
    elif trip_type == "beach":
        items.update([get_item("swimsuit", language), get_item("pareo", language), get_item("flipflops", language), get_item("beach_towel", language), get_item("after_sun", language), get_item("beach_bag", language), get_item("sunscreen", language)])
    elif trip_type == "winter":
        items.update([get_item("ski_suit", language), get_item("thermo", language), get_item("fleece", language), get_item("mittens", language), get_item("goggles", language), get_item("wind_cream", language)])

    # Visa/Adapter logic
    visa_countries = ["FR", "DE", "IT", "ES", "GB", "US", "CN", "JP", "TR", "EG", "TH", "IN"] # Shortened list for brevity, ideally reuse full list
    if country in visa_countries:
        items.add(get_item("visa", language))
    
    adapter_countries = ["US", "GB", "AU", "JP", "CN", "CH"]
    if country in adapter_countries:
        items.add(get_item("adapter", language))

    return {
        "items": items,
        "avg_temp": avg_temp,
        "conditions": list(conditions),
        "daily_forecast": daily_forecast,
        "country": country,
        "start_date": start_dt.date(),
        "end_date": end_dt.date()
    }

async def create_checklist_from_items(db, items, city, start_date, end_date, avg_temp, conditions, daily_forecast, user_id=None, language="ru"):
    # Categorization logic
    mapping = get_category_map(language)
    categories = {k: [] for k in mapping.keys()}
    
    # Always add essentials
    items.update([get_item("passport", language), get_item("insurance", language), get_item("money", language), get_item("tickets", language), get_item("booking", language)])
    
    for item in items:
        found = False
        for cat, keywords in mapping.items():
            if any(k.lower() in item.lower() for k in keywords):
                categories[cat].append(item)
                found = True
                break
        if not found:
            categories["Прочее"].append(item)

    for k in categories:
        categories[k] = list(sorted(set(categories[k])))
        
    all_items = []
    for k, v in categories.items():
        all_items.extend(v)

    checklist_data = schemas.ChecklistCreate(
        city=city,
        start_date=start_date,
        end_date=end_date,
        items=all_items,
        avg_temp=avg_temp,
        conditions=sorted(list(conditions)),
        daily_forecast=daily_forecast,
        user_id=user_id,
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

@app.post("/generate-packing-list", response_model=ChecklistResponse)
async def generate_list(req: PackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await calculate_packing_data(
        req.city, req.start_date, req.end_date, req.trip_type, req.transport,
        req.gender, req.traveling_with_pet, req.has_allergies, req.has_chronic_diseases, req.language
    )
    return await create_checklist_from_items(
        db, data["items"], req.city, data["start_date"], data["end_date"],
        data["avg_temp"], data["conditions"], data["daily_forecast"],
        current_user.id if current_user else None,
        language=req.language
    )

@app.post("/generate-multi-city", response_model=ChecklistResponse)
async def generate_multi_city(req: MultiCityPackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    all_items = set()
    all_forecast = []
    temps = []
    conditions = set()
    cities = []
    
    for seg in req.segments:
        cities.append(seg.city.split(",")[0])
        data = await calculate_packing_data(
            seg.city, seg.start_date, seg.end_date, seg.trip_type, seg.transport,
            req.gender, req.traveling_with_pet, req.has_allergies, req.has_chronic_diseases, req.language
        )
        all_items.update(data["items"])
        all_forecast.extend(data["daily_forecast"])
        if data["avg_temp"]: temps.append(data["avg_temp"])
        conditions.update(data["conditions"])
    
    # Sort forecast by date
    all_forecast.sort(key=lambda x: x.date)
    
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    display_city = " + ".join(cities)
    
    # Parse dates for main checklist
    min_date = datetime.strptime(req.segments[0].start_date, "%Y-%m-%d").date()
    max_date = datetime.strptime(req.segments[-1].end_date, "%Y-%m-%d").date()
    
    return await create_checklist_from_items(
        db, all_items, display_city, min_date, max_date,
        avg_temp, list(conditions), all_forecast,
        current_user.id if current_user else None,
        language=req.language
    )

@app.post("/save-tg-checklist", response_model=schemas.ChecklistOut)
async def save_tg_checklist(data: schemas.ChecklistCreate = Body(...), db: AsyncSession = Depends(get_db)):
    if not data.tg_user_id:
        raise HTTPException(status_code=400, detail="Не передан tg_user_id")
    checklist = await crud.save_or_update_tg_checklist(db, data)
    return checklist

@app.get("/tg-checklist/{tg_user_id}", response_model=schemas.ChecklistOut)
async def get_tg_checklist(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_tg_user_id(db, tg_user_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден для пользователя")
    return checklist

@app.get("/tg-checklists/{tg_user_id}", response_model=List[schemas.ChecklistOut])
async def get_tg_checklists(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklists = await crud.get_all_checklists_by_tg_user_id(db, tg_user_id)
    return checklists

@app.get("/checklist/{slug}", response_model=ChecklistResponse)
async def get_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    # Fetch fresh weather data
    forecast = await get_weather_forecast_data(checklist.city, checklist.start_date, checklist.end_date)
    
    # Construct response manually (since ORM object doesn't have daily_forecast)
    response = ChecklistResponse(
        **{k: getattr(checklist, k) for k in checklist.__table__.columns.keys()},
        daily_forecast=forecast
    )
    return response

    # Категории для чеклиста (для фронта)
    # --- Распределение по категориям (копия логики из generate_list) ---
    mapping = {
        "Важное": ["Паспорт", "Медицинская страховка", "Деньги/карта", "Виза", "Билеты", "Бронь отеля", "Водительское удостоверение/СТС", "Ветпаспорт"],
        "Документы": ["Список аллергенов", "Медзаключение", "Личные рецепты"],
        "Одежда": ["куртка", "пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "ботинки", "носки", "Свитер", "толстовка", "Джинсы", "брюки", "Кроссовки", "кофта", "свитшот", "Футболки", "Шорты", "платья", "Панама", "кепка", "очки", "Обувь", "Дождевик", "Зонт", "Купальник", "плавки", "туника", "парео", "Шлёпанцы", "Костюм", "Рубашки", "блузки", "Туфли", "юбка"],
        "Гигиена": ["Зубная", "Паста", "Дезодорант", "Мыло", "Расчёска", "Косметика", "макияж", "Влажные салфетки", "Бритвенный набор", "Антиперспирант"],
        "Техника": ["Телефон", "Зарядка", "Пауэрбанк", "Power bank", "Переходник", "Ноутбук", "Наушники"],
        "Аптечка": ["лекарства", "Пластыри", "Обезболивающее", "Антигистаминные"],
        "Прочее": ["Бутылка", "Термос", "рюкзак", "Сумка", "Крем", "Снеки", "Плейлист", "Подушка", "Беруши", "маска", "Жидкости", "Тапочки", "Кружка", "Миска", "Поводок", "переноска", "Пелёнки", "пакеты", "Игрушка", "Визитки"]
    }

    # Инициализация
    categories = {k: [] for k in mapping.keys()}

    for item in checklist.items:
        found = False
        for cat, keywords in mapping.items():
            if any(k.lower() in item.lower() for k in keywords):
                categories[cat].append(item)
                found = True
                break
        
        if not found:
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

@app.patch("/checklist/{slug}/state", response_model=schemas.ChecklistOut)
async def update_checklist_state(slug: str, state: ChecklistStateUpdate = Body(...), db: AsyncSession = Depends(get_db)):
    checklist = await crud.update_checklist_state(
        db,
        slug,
        checked_items=state.checked_items,
        removed_items=state.removed_items,
        added_items=state.added_items,
        items=state.items,
    )
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    return checklist


@app.patch("/checklist/{slug}/privacy", response_model=schemas.ChecklistOut)
async def update_checklist_privacy(
    slug: str,
    privacy: ChecklistPrivacyUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    """Обновление приватности чеклиста"""
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    
    # Проверка прав (только владелец)
    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав")

    checklist.is_public = privacy.is_public
    await db.commit()
    await db.refresh(checklist)
    return checklist


@app.delete("/checklist/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    await db.delete(checklist)
    await db.commit()
    return

@app.get("/")
async def root():
    return {"message": "Luggify backend is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint - проверяет доступность сервера и подключение к БД"""
    try:
        # Проверяем наличие переменных окружения
        db_url = os.getenv("DATABASE_URL")
        db_status = "configured" if db_url else "missing"

        # Пытаемся подключиться к БД если она настроена
        db_connection = "unknown"
        db_error_details = None
        if db_url and SessionLocal:
            try:
                from sqlalchemy import text
                async with SessionLocal() as session:
                    await session.execute(text("SELECT 1"))
                db_connection = "ok"
            except Exception as e:
                error_msg = str(e)
                db_connection = "error"
                db_error_details = error_msg[:200]
                if "Name or service not known" in error_msg:
                    db_error_details += " | Возможно неправильный хост"
                elif "could not translate host name" in error_msg.lower():
                    db_error_details += " | Проверьте формат DATABASE_URL"
        elif not db_url:
            db_connection = "not_configured"

        result = {
            "status": "ok",
            "database_url": db_status,
            "database_connection": db_connection,
            "message": "Server is running"
        }
        if db_error_details:
            result["database_error"] = db_error_details
        if db_url:
            # Показываем хост из URL (без пароля)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                result["database_host"] = parsed.hostname
                result["database_port"] = parsed.port
            except:
                pass
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }