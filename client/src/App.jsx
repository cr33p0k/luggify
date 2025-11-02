import React, { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";

import "./App.css";

const App = () => {
  const { id } = useParams(); // slug из URL
  const navigate = useNavigate();
  const location = useLocation();

  const [city, setCity] = useState(null);
  const [dates, setDates] = useState({ start: null, end: null });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [savedSlug, setSavedSlug] = useState(null);

  // Состояние для чеклиста
  const [checkedItems, setCheckedItems] = useState({});
  // Состояние для удалённых вещей
  const [removedItems, setRemovedItems] = useState([]);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");

  useEffect(() => {
    const fetchChecklistAndForecast = async () => {
      try {
        const res = await fetch(`https://luggify.onrender.com/checklist/${id}`);
        if (!res.ok) {
          const errorText = await res.text();
          let errorMessage = "Чеклист не найден";
          try {
            const errorData = JSON.parse(errorText);
            errorMessage = errorData.detail || errorMessage;
          } catch (e) {
            // Используем стандартное сообщение если не удалось распарсить
          }
          throw new Error(errorMessage);
        }

        const data = await res.json();
        setCity({ fullName: data.city });
        setDates({ start: data.start_date, end: data.end_date });

        // Получаем координаты
        let daily_forecast = [];
        try {
          const geoRes = await fetch(
            `https://api.openweathermap.org/geo/1.0/direct?q=${encodeURIComponent(
              data.city
            )}&limit=1&appid=${import.meta.env.VITE_WEATHER_API_KEY}`
          );
          if (!geoRes.ok) {
            console.warn("Не удалось получить координаты города");
          } else {
            const geoData = await geoRes.json();
            if (geoData.length > 0) {
              const { lat, lon } = geoData[0];

              // Получаем прогноз через 16-дневный API
              const start = new Date(data.start_date);
              const end = new Date(data.end_date);
              const daysCount = Math.min(
                Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1,
                16
              );
              const forecastRes = await fetch(
                `https://api.openweathermap.org/data/2.5/forecast/daily?lat=${lat}&lon=${lon}&cnt=${daysCount}&units=metric&appid=${import.meta.env.VITE_WEATHER_API_KEY}`
              );
              if (forecastRes.ok) {
                const forecastData = await forecastRes.json();

                const translated = {
                  // Thunderstorm
                  "thunderstorm with light rain": "Гроза с небольшим дождём",
                  "thunderstorm with rain": "Гроза с дождём",
                  "thunderstorm with heavy rain": "Гроза с сильным дождём",
                  "light thunderstorm": "Слабая гроза",
                  "thunderstorm": "Гроза",
                  "heavy thunderstorm": "Сильная гроза",
                  "ragged thunderstorm": "Местами гроза",
                  "thunderstorm with light drizzle": "Гроза с небольшим моросящим дождём",
                  "thunderstorm with drizzle": "Гроза с моросящим дождём",
                  "thunderstorm with heavy drizzle": "Гроза с сильным моросящим дождём",
                  // Drizzle
                  "light intensity drizzle": "Лёгкая морось",
                  "drizzle": "Морось",
                  "heavy intensity drizzle": "Сильная морось",
                  "light intensity drizzle rain": "Лёгкий моросящий дождь",
                  "drizzle rain": "Моросящий дождь",
                  "heavy intensity drizzle rain": "Сильный моросящий дождь",
                  "shower rain and drizzle": "Ливень и морось",
                  "heavy shower rain and drizzle": "Сильный ливень и морось",
                  "shower drizzle": "Моросящий ливень",
                  // Rain
                  "light rain": "Лёгкий дождь",
                  "moderate rain": "Умеренный дождь",
                  "heavy intensity rain": "Сильный дождь",
                  "very heavy rain": "Очень сильный дождь",
                  "extreme rain": "Экстремальный дождь",
                  "freezing rain": "Ледяной дождь",
                  "light intensity shower rain": "Лёгкий ливневый дождь",
                  "shower rain": "Ливневый дождь",
                  "heavy intensity shower rain": "Сильный ливневый дождь",
                  "ragged shower rain": "Местами ливневый дождь",
                  // Snow
                  "light snow": "Лёгкий снег",
                  "snow": "Снег",
                  "heavy snow": "Сильный снег",
                  "sleet": "Дождь со снегом",
                  "light shower sleet": "Лёгкий ливневый дождь со снегом",
                  "shower sleet": "Ливневый дождь со снегом",
                  "light rain and snow": "Лёгкий дождь и снег",
                  "rain and snow": "Дождь и снег",
                  "light shower snow": "Лёгкий ливневый снег",
                  "shower snow": "Ливневый снег",
                  "heavy shower snow": "Сильный ливневый снег",
                  // Atmosphere
                  "mist": "Туман",
                  "smoke": "Дымка",
                  "haze": "Мгла",
                  "sand/dust whirls": "Песчаные/пылевые вихри",
                  "fog": "Туман",
                  "sand": "Песок",
                  "dust": "Пыль",
                  "volcanic ash": "Вулканический пепел",
                  "squalls": "Шквалы",
                  "tornado": "Торнадо",
                  // Clear
                  "clear sky": "Ясно",
                  // Clouds
                  "few clouds": "Малооблачно",
                  "scattered clouds": "Облачно",
                  "broken clouds": "Пасмурно",
                  "overcast clouds": "Пасмурно",
                  "sky is clear": "Ясно",
                };

                // Формируем daily_forecast из 16-дневного API
                daily_forecast = (forecastData.list || []).map((entry) => {
                  const date = new Date(entry.dt * 1000);
                  return {
                    date: date.toISOString().split("T")[0],
                    temp_min: entry.temp.min,
                    temp_max: entry.temp.max,
                    conditions:
                      translated[entry.weather[0].description.toLowerCase()] ??
                      entry.weather[0].description,
                    icon: entry.weather[0].icon,
                  };
                }).filter(day => {
                  // Оставляем только дни в выбранном диапазоне
                  const d = new Date(day.date);
                  return d >= start && d <= end;
                });
              } else {
                console.warn("Не удалось получить прогноз погоды");
              }
            }
          }
        } catch (e) {
          console.warn("Ошибка при получении прогноза погоды:", e);
        }

        setResult({
          ...data,
          daily_forecast,
        });
        setSavedSlug(id);
      } catch (e) {
        console.error(e);
        setError("Ошибка при загрузке сохраненного чеклиста");
      }
    };

    if (id) {
      fetchChecklistAndForecast();
    }
  }, [id]);

  // Загружаем отмеченные из localStorage при загрузке чеклиста
  useEffect(() => {
    if (result && result.items && savedSlug) {
      const saved = JSON.parse(localStorage.getItem(`checkedItems_${savedSlug}`) || "{}");
      const initial = {};
      result.items.forEach(item => {
        initial[item] = saved[item] || false;
      });
      setCheckedItems(initial);
    }
  }, [result, savedSlug]);

  // Сохраняем отмеченные в localStorage при изменении
  useEffect(() => {
    if (savedSlug) {
      localStorage.setItem(`checkedItems_${savedSlug}`, JSON.stringify(checkedItems));
    }
  }, [checkedItems, savedSlug]);

  // Загружаем удалённые вещи из localStorage при загрузке чеклиста
  useEffect(() => {
    if (savedSlug) {
      const removed = JSON.parse(localStorage.getItem(`removedItems_${savedSlug}`) || "[]");
      setRemovedItems(removed);
    }
  }, [savedSlug]);

  // Сохраняем удалённые вещи в localStorage при изменении
  useEffect(() => {
    if (savedSlug) {
      localStorage.setItem(`removedItems_${savedSlug}`, JSON.stringify(removedItems));
    }
  }, [removedItems, savedSlug]);

  useEffect(() => {
    if (location.pathname === "/") {
      setSavedSlug(null);
      setResult(null);
      setCity(null);
      setDates({ start: null, end: null });
      setError(null);
    }
  }, [location.pathname]);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    setSavedSlug(null);

    if (!city || !dates.start || !dates.end) {
      alert("Заполните все поля!");
      return;
    }

    const start = new Date(dates.start);
    const end = new Date(dates.end);
    const diffDays = (end - start) / (1000 * 60 * 60 * 24) + 1;

    if (diffDays > 16) {
      alert("Период поездки не может превышать 16 дней");
      return;
    }

    try {
      const res = await fetch("https://luggify.onrender.com/generate-packing-list", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: city.fullName,
          start_date: dates.start,
          end_date: dates.end,
        }),
      });

      if (!res.ok) {
        let errorMessage = "Ошибка при генерации списка";
        try {
          const errorData = await res.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          // Если не удалось распарсить JSON, используем стандартное сообщение
          errorMessage = `Ошибка ${res.status}: ${res.statusText}`;
        }
        setError(errorMessage);
        return;
      }

      const data = await res.json();

      if (!data.slug) {
        setError("Сервер не вернул slug чеклиста");
        return;
      }

      setResult(data);
      setSavedSlug(data.slug);
      navigate(`/checklist/${data.slug}`);
    } catch (e) {
      setError("Ошибка при запросе к серверу");
    }
  };

  const copyToClipboard = () => {
    if (!savedSlug) return;
    const url = `${window.location.origin}/checklist/${savedSlug}`;
    navigator.clipboard
      .writeText(url)
      .then(() => alert("Ссылка скопирована!"))
      .catch(() => alert("Не удалось скопировать ссылку"));
  };

  const handleCheck = (item) => {
    setCheckedItems(prev => ({
      ...prev,
      [item]: !prev[item]
    }));
  };

  const handleRemoveItem = (item) => {
    setRemovedItems(prev => [...prev, item]);
  };

  const handleRestoreAll = () => {
    setRemovedItems([]);
  };

  const resetChecklist = () => {
    const reset = {};
    result.items.forEach(item => {
      reset[item] = false;
    });
    setCheckedItems(reset);
  };

  const handleAddItem = () => {
    if (!newItem.trim()) return;
    if (result.items.includes(newItem.trim())) return;
    setResult(prev => ({
      ...prev,
      items: [...prev.items, newItem.trim()]
    }));
    setNewItem("");
    setAddItemMode(false);
  };

  const formatDate = (isoDate) => {
    const d = new Date(isoDate);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}.${month}.${year}`;
  };

  return (
    <div className={`container large ${result ? "expanded" : ""}`}>
      <h1
        style={{ cursor: "pointer", userSelect: "none" }}
        onClick={() => navigate("/")}
      >
        Luggify
      </h1>

      {!savedSlug && (
        <>
          <div className="input-group">
            <CitySelect value={city} onSelect={setCity} />
          </div>

          <DateRangePicker onChange={(newDates) => setDates(newDates)} />

          <button onClick={handleSubmit}>Сгенерировать список</button>
        </>
      )}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          {/* Многостолбцовый чеклист по категориям */}
          {(() => {
            const isMobile = window.innerWidth <= 700;
            const isTablet = window.innerWidth > 700 && window.innerWidth <= 1100;
            let items = (result.items || []).filter(item => !removedItems.includes(item));
            let columns = 3;
            if (isTablet) columns = 2;
            if (isMobile) columns = 1;
            const perCol = Math.ceil(items.length / columns);
            const cols = Array.from({ length: columns }, (_, i) => items.slice(i * perCol, (i + 1) * perCol));
            return (
              <>
                <div className="checklist-multicolumn">
                  {cols.map((col, idx) => (
                    <div className="checklist-category" key={idx}>
                      <div className="checklist">
                        {col.map((item) => (
                          <label
                            key={item}
                            className={`checklist-label${checkedItems[item] ? " checked" : ""}`}
                          >
                            <input
                              type="checkbox"
                              className="checklist-checkbox"
                              checked={checkedItems[item] || false}
                              onChange={() => handleCheck(item)}
                            />
                            {item}
                            <button
                              className="checklist-remove-btn"
                              title="Удалить из чеклиста"
                              onClick={e => { e.preventDefault(); handleRemoveItem(item); }}
                              tabIndex={-1}
                            >×</button>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="checklist-actions">
                  <button className="checklist-reset-btn" onClick={resetChecklist}>Сбросить отметки</button>
                  <button className="checklist-reset-btn" onClick={() => setAddItemMode(v => !v)}>
                    {addItemMode ? "Отмена" : "Добавить вещь"}
                  </button>
                  {addItemMode && (
                    <>
                      <input
                        className="add-item-input"
                        type="text"
                        value={newItem}
                        onChange={e => setNewItem(e.target.value)}
                        placeholder="Новая вещь"
                        onKeyDown={e => { if (e.key === "Enter") handleAddItem(); }}
                        autoFocus
                        style={{ marginLeft: 10, marginRight: 10, padding: "0.3rem 0.7rem", borderRadius: 8, border: "1.5px solid orange", fontSize: "1rem" }}
                      />
                      <button className="checklist-reset-btn" style={{padding: "0.3rem 1.1rem"}} onClick={handleAddItem}>ОК</button>
                    </>
                  )}
                  {removedItems.length > 0 && (
                    <button className="checklist-reset-btn" onClick={handleRestoreAll}>
                      Восстановить вещи
                    </button>
                  )}
                </div>
              </>
            );
          })()}

          {/* Кнопки управления чеклистом */}
          {/* <div className="checklist-actions">
            {removedItems.length > 0 && (
              <button className="checklist-reset-btn" onClick={handleRestoreAll}>
                Восстановить вещи
              </button>
            )}
            <button className="checklist-reset-btn" onClick={resetChecklist}>Сбросить отметки</button>
          </div> */}

          {/* Прогноз погоды */}
          {result.daily_forecast && result.daily_forecast.length > 0 && (
          <div className="forecast">
            <h3>Прогноз погоды</h3>
            <div className="forecast-grid">
              {result.daily_forecast.map((day) => (
                <div key={day.date} className="forecast-card">
                  <div className="forecast-date">{formatDate(day.date)}</div>
                  <img
                    src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                    alt={day.conditions}
                    className="forecast-icon"
                  />
                  <div className="forecast-conditions">{day.conditions}</div>
                  <div className="forecast-temp">
                    {day.temp_min.toFixed(1)}° / {day.temp_max.toFixed(1)}°C
                  </div>
                </div>
              ))}
            </div>
          </div>
          )}

          {savedSlug && (
            <div className="share-box">
              <p>Чеклист сохранён! Ваша ссылка:</p>
              <div className="link-box">
                <a
                  href={`/checklist/${savedSlug}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {window.location.origin}/checklist/{savedSlug}
                </a>
              </div>
              <button className="copy-button" onClick={copyToClipboard}>
                Копировать ссылку
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default App;
