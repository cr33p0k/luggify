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

# Nominatim (OpenStreetMap) — геокодинг с русским языком
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# WMO Weather Codes -> русские описания + иконки
WMO_CODES = {
    0: ("Ясно", "01d"),
    1: ("Преимущественно ясно", "02d"),
    2: ("Переменная облачность", "03d"),
    3: ("Пасмурно", "04d"),
    45: ("Туман", "50d"),
    48: ("Изморозь", "50d"),
    51: ("Лёгкая морось", "09d"),
    53: ("Умеренная морось", "09d"),
    55: ("Сильная морось", "09d"),
    61: ("Небольшой дождь", "10d"),
    63: ("Умеренный дождь", "10d"),
    65: ("Сильный дождь", "10d"),
    66: ("Ледяной дождь", "13d"),
    67: ("Сильный ледяной дождь", "13d"),
    71: ("Небольшой снег", "13d"),
    73: ("Умеренный снег", "13d"),
    75: ("Сильный снег", "13d"),
    77: ("Снежные зёрна", "13d"),
    80: ("Лёгкий ливень", "09d"),
    81: ("Умеренный ливень", "09d"),
    82: ("Сильный ливень", "09d"),
    85: ("Снегопад", "13d"),
    86: ("Сильный снегопад", "13d"),
    95: ("Гроза", "11d"),
    96: ("Гроза с градом", "11d"),
    99: ("Гроза с сильным градом", "11d"),
}

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

class DailyForecastItem(BaseModel):
    date: str
    temp_min: float
    temp_max: float
    condition: str
    icon: str
    source: str = "forecast"  # "forecast" или "historical"

class ChecklistResponse(schemas.ChecklistOut):
    daily_forecast: list[DailyForecastItem]

class ChecklistStateUpdate(BaseModel):
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    items: Optional[List[str]] = None

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


@app.get("/my-checklists", response_model=List[schemas.ChecklistOut])
async def get_my_checklists(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получение всех чеклистов текущего пользователя"""
    checklists = await crud.get_checklists_by_user_id(db, user.id)
    return checklists


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
                        desc, icon = WMO_CODES.get(codes[i], ("Неизвестно", "01d"))
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

@app.post("/generate-packing-list", response_model=ChecklistResponse)
async def generate_list(req: PackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    # --- Геокодинг через Nominatim ---
    async with httpx.AsyncClient() as client:
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        geo_resp = await client.get(NOMINATIM_URL, params={
            "q": req.city.split(",")[0].strip(),
            "format": "json",
            "accept-language": "ru",
            "limit": 1,
            "addressdetails": 1,
        }, headers=headers)
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if not geo_data:
            raise HTTPException(status_code=404, detail="Город не найден")

        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])
        addr = geo_data[0].get("address", {})
        country = addr.get("country_code", "").upper()

        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(req.end_date, "%Y-%m-%d")
        days_count = (end_dt - start_dt).days + 1
        today = datetime.now().date()

        # --- Гибридный прогноз: Forecast (≤16 дней) + Historical (>16 дней) ---
        forecast_limit = today + timedelta(days=15)  # последний день прогноза

        daily_data = {}  # date_str -> {temp_min, temp_max, weathercode}

        # 1) Open-Meteo Forecast (до 16 дней вперёд)
        if start_dt.date() <= forecast_limit:
            forecast_end = min(end_dt.date(), forecast_limit)
            forecast_resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": forecast_end.strftime("%Y-%m-%d"),
            })
            forecast_resp.raise_for_status()
            f_data = forecast_resp.json().get("daily", {})
            times = f_data.get("time", [])
            t_max = f_data.get("temperature_2m_max", [])
            t_min = f_data.get("temperature_2m_min", [])
            codes = f_data.get("weathercode", [])
            for i, date_str in enumerate(times):
                daily_data[date_str] = {
                    "temp_max": t_max[i] if i < len(t_max) else 0,
                    "temp_min": t_min[i] if i < len(t_min) else 0,
                    "weathercode": codes[i] if i < len(codes) else 0,
                    "source": "forecast",
                }

        # 2) Open-Meteo Historical (для дат за пределами 16-дневного прогноза)
        hist_start = max(start_dt.date(), forecast_limit + timedelta(days=1))
        if hist_start <= end_dt.date():
            # Берём те же даты за прошлый год
            hist_start_ly = hist_start.replace(year=hist_start.year - 1)
            hist_end_ly = end_dt.date().replace(year=end_dt.year - 1)
            hist_resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "timezone": "auto",
                "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                "end_date": hist_end_ly.strftime("%Y-%m-%d"),
            })
            hist_resp.raise_for_status()
            h_data = hist_resp.json().get("daily", {})
            h_times = h_data.get("time", [])
            h_t_max = h_data.get("temperature_2m_max", [])
            h_t_min = h_data.get("temperature_2m_min", [])
            h_codes = h_data.get("weathercode", [])
            for i, date_str_ly in enumerate(h_times):
                # Переносим дату на текущий год
                d = datetime.strptime(date_str_ly, "%Y-%m-%d").date()
                actual_date = d.replace(year=d.year + 1)
                actual_date_str = actual_date.strftime("%Y-%m-%d")
                if actual_date_str not in daily_data:  # не перезаписываем forecast
                    daily_data[actual_date_str] = {
                        "temp_max": h_t_max[i] if i < len(h_t_max) else 0,
                        "temp_min": h_t_min[i] if i < len(h_t_min) else 0,
                        "weathercode": h_codes[i] if i < len(h_codes) else 0,
                        "source": "historical",
                    }

    # --- Обработка погодных данных ---
    items = set()
    items.update([
        "Паспорт", "Медицинская страховка", "Зарядка для телефона",
        "Телефон", "Деньги/карта", "Средства гигиены",
        "Одежда на каждый день", "Нижнее бельё", "Носки",
        "Зубная щётка и паста", "Дезодорант", "Личные лекарства",
        "Сумка/рюкзак", "Полотенце (если не предоставляется)",
        "Бутылка для воды", "Маска/антисептик",
    ])

    temps = []
    conditions = set()
    daily_forecast = []

    for date_str in sorted(daily_data.keys()):
        d = daily_data[date_str]
        temp_avg = (d["temp_max"] + d["temp_min"]) / 2
        wmo_code = d["weathercode"]
        cond_ru, icon = WMO_CODES.get(wmo_code, ("Неизвестно", "03d"))
        source = d["source"]

        temps.append(temp_avg)
        conditions.add(cond_ru)

        # Одежда по температуре
        if temp_avg < 0:
            items.update(["Тёплая куртка/пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "Тёплые носки", "Зимние ботинки"])
        elif temp_avg < 10:
            items.update(["Лёгкая куртка/ветровка", "Свитер/толстовка", "Джинсы/брюки", "Кроссовки/ботинки"])
        elif temp_avg < 20:
            items.update(["Лёгкая кофта/свитшот", "Футболки", "Джинсы/брюки", "Кроссовки"])
        else:
            items.update(["Футболки", "Шорты/лёгкие платья", "Панама/кепка", "Солнцезащитные очки", "Легкая обувь"])

        # Осадки по WMO-коду
        if wmo_code in (51, 53, 55, 61, 63, 65, 66, 67, 80, 81, 82):
            items.add("Зонт или дождевик")
            items.add("Водонепроницаемая обувь")
        if wmo_code in (71, 73, 75, 77, 85, 86):
            items.add("Тёплая обувь")
        if temp_avg > 20:
            items.add("Солнцезащитный крем")

        daily_forecast.append(DailyForecastItem(
            date=date_str,
            temp_min=d["temp_min"],
            temp_max=d["temp_max"],
            condition=cond_ru,
            icon=icon,
            source=source,
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
    # country уже установлен выше из geo_data[0].get("country_code")
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
    # Переходник для розеток (ISO-2)
    adapter_countries = [
        "US", "GB", "AU", "JP", "CN", "CH"
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
        daily_forecast=daily_forecast,
        user_id=current_user.id if current_user else None,
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