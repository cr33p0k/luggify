import React, { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";
import AuthModal from "./AuthModal";
import ProfilePage from "./ProfilePage";

import "./App.css";
import "./AuthModal.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TRANSLATIONS = {
  ru: {
    heroTitle: "Куда собираемся?",
    heroSubtitle: "Введите город и даты — мы соберём идеальный чеклист для вашей поездки",
    addCity: "+ Добавить город",
    generate: "🚀 Поехали!",
    transport: "Транспорт:",
    gender: "Пол:",
    tripType: "Тип поездки:",
    pet: "🐾 С питомцем",
    allergies: "🤧 Аллергия",
    meds: "💊 Лекарства",
    forecast: "🌤 Прогноз погоды",
    humidity: "Влажность",
    uv: "УФ-индекс",
    wind: "Ветер",
    kmh: "км/ч",
    errorChecklist: "Ошибка при загрузке чеклиста",
    errorServer: "Ошибка при запросе к серверу",
    fillAll: "Заполните все города и даты!",
    login: "Войти",
    logout: "Выйти",
    saveSuccess: "✅ Чеклист сохранён в вашем аккаунте!",
    saveError: "❌ Ошибка сохранения",
    restore: "Восстановить удалённые",
    reset: "Сбросить отметки",
    addItem: "+ Добавить вещь",
    cancel: "Отмена",
    newItem: "Новая вещь",
    // Options
    plane: "✈️ Самолёт",
    train: "🚆 Поезд",
    car: "🚗 Авто",
    bus: "🚌 Автобус",
    unisex: "🚻 Любой",
    male: "👨 Мужской",
    female: "👩 Женский",
    vacation: "🌴 Отдых",
    business: "💼 Работа",
    active: "🏃 Активный",
    beach: "🏖 Пляж",
    winter: "🎿 Зима",
  },
  en: {
    heroTitle: "Where to?",
    heroSubtitle: "Enter city and dates — we'll generate the perfect packing list for your trip",
    addCity: "+ Add City",
    generate: "🚀 Let's go!",
    transport: "Transport:",
    gender: "Gender:",
    tripType: "Trip Type:",
    pet: "🐾 With Pet",
    allergies: "🤧 Allergies",
    meds: "💊 Chronic Disease",
    forecast: "🌤 Weather Forecast",
    humidity: "Humidity",
    uv: "UV Index",
    wind: "Wind",
    kmh: "km/h",
    errorChecklist: "Error loading checklist",
    errorServer: "Server connection error",
    fillAll: "Please fill in all cities and dates!",
    login: "Login",
    logout: "Logout",
    saveSuccess: "✅ Checklist saved to your account!",
    saveError: "❌ Save error",
    restore: "Restore removed items",
    reset: "Reset checks",
    addItem: "+ Add Item",
    cancel: "Cancel",
    newItem: "New item",
    // Options
    plane: "✈️ Plane",
    train: "🚆 Train",
    car: "🚗 Car",
    bus: "🚌 Bus",
    unisex: "🚻 Any",
    male: "👨 Male",
    female: "👩 Female",
    vacation: "🌴 Vacation",
    business: "💼 Business",
    active: "🏃 Active",
    beach: "🏖 Beach",
    winter: "🎿 Winter",
  }
};

const App = ({ page }) => {
  const { id } = useParams(); // slug из URL
  const navigate = useNavigate();
  const location = useLocation();

  const [lang, setLang] = useState("ru");
  const t = TRANSLATIONS[lang];

  const [destinations, setDestinations] = useState([
    { id: 1, city: null, dates: { start: null, end: null } }
  ]);
  const [options, setOptions] = useState({
    trip_type: "vacation",
    gender: "unisex", // new
    transport: "plane", // new
    traveling_with_pet: false,
    has_allergies: false,
    has_chronic_diseases: false,
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [savedSlug, setSavedSlug] = useState(null);

  // Состояние для чеклиста
  const [checkedItems, setCheckedItems] = useState({});
  // Состояние для удалённых вещей
  const [removedItems, setRemovedItems] = useState([]);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");

  // Auth state
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [showAuth, setShowAuth] = useState(false);

  const handleAuth = (userData, accessToken) => {
    setUser(userData);
    setToken(accessToken);
  };

  const handleLogout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  };

  const authHeaders = token
    ? { "Authorization": `Bearer ${token}` }
    : {};

  useEffect(() => {
    const fetchChecklist = async () => {
      try {
        const res = await fetch(`${API_URL}/checklist/${id}`);
        if (!res.ok) throw new Error("Чеклист не найден");
        const data = await res.json();
        setCity({ fullName: data.city });
        setDates({ start: data.start_date, end: data.end_date });
        setResult(data);
        setSavedSlug(id);
      } catch (e) {
        console.error(e);
        setError("Ошибка при загрузке чеклиста");
      }
    };

    if (id) {
      fetchChecklist();
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
      setDestinations([{ id: 1, city: null, dates: { start: null, end: null } }]);
      setError(null);
    }
  }, [location.pathname]);

  const handleAddDestination = () => {
    setDestinations([
      ...destinations,
      { id: Date.now(), city: null, dates: { start: null, end: null } }
    ]);
  };

  const handleRemoveDestination = (id) => {
    if (destinations.length > 1) {
      setDestinations(destinations.filter(d => d.id !== id));
    }
  };

  const updateDestination = (id, field, value) => {
    setDestinations(prev => prev.map(d => {
      if (d.id === id) {
        return { ...d, [field]: value };
      }
      return d;
    }));
  };

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    setSavedSlug(null);

    // Валидация
    const isValid = destinations.every(d => d.city && d.dates.start && d.dates.end);
    if (!isValid) {
      alert("Заполните все города и даты!");
      return;
    }

    try {
      const payload = {
        segments: destinations.map(d => ({
          city: d.city.fullName,
          start_date: d.dates.start,
          end_date: d.dates.end,
          trip_type: options.trip_type, // Global for now
          transport: options.transport, // Global for now
        })),
        gender: options.gender,
        traveling_with_pet: options.traveling_with_pet,
        has_allergies: options.has_allergies,
        has_chronic_diseases: options.has_chronic_diseases,
        language: lang,
      };

      const res = await fetch(`${API_URL}/generate-multi-city`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        setError(errorData.detail || "Ошибка при генерации списка");
        return;
      }

      const data = await res.json();

      setResult(data);
      setSavedSlug(data.slug || null);
    } catch (e) {
      setError("Ошибка при запросе к серверу");
    }
  };

  const [saveMsg, setSaveMsg] = useState(null);

  const handleSaveToAccount = async () => {
    if (!user || !token) {
      setShowAuth(true);
      return;
    }
    setSaveMsg(null);
    try {
      // Чеклист уже сохранён на сервере при генерации, просто показываем подтверждение
      setSaveMsg("✅ Чеклист сохранён в вашем аккаунте!");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch (e) {
      setSaveMsg("❌ Ошибка сохранения");
    }
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
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-logo" onClick={() => navigate("/")}>
          <span>🧳</span> Luggify
        </div>
        <div className="navbar-user">
          <div className="language-switcher">
            <button
              className={`lang-btn ${lang === "ru" ? "active" : ""}`}
              onClick={() => setLang("ru")}
            >RU</button>
            <button
              className={`lang-btn ${lang === "en" ? "active" : ""}`}
              onClick={() => setLang("en")}
            >EN</button>
          </div>
          {user ? (
            <>
              <div className="navbar-profile" onClick={() => navigate("/profile")}>
                <div className="navbar-avatar">
                  {user.username.charAt(0).toUpperCase()}
                </div>
                <span className="navbar-username">{user.username}</span>
              </div>
              <button
                className="navbar-logout-btn icon-btn"
                onClick={handleLogout}
                title={t.logout}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </>
          ) : (
            <button className="navbar-login-btn" onClick={() => setShowAuth(true)}>{t.login}</button>
          )}
        </div>
      </nav>

      {showAuth && (
        <AuthModal
          onClose={() => setShowAuth(false)}
          onAuth={handleAuth}
        />
      )}

      <div className="page-wrapper">
        {/* Profile Page */}
        {page === "profile" ? (
          <ProfilePage user={user} token={token} onLogout={handleLogout} />
        ) : (
          <>
            {!result && (
              <>
                <div className="hero">
                  <h2>{t.heroTitle}</h2>
                  <p>{t.heroSubtitle}</p>
                </div>

                <div className="form-card">
                  {destinations.map((dest, index) => (
                    <div key={dest.id} className="destination-row">
                      <div className="destination-header">
                        {destinations.length > 1 && <span className="destination-number">#{index + 1}</span>}
                        {destinations.length > 1 && (
                          <button
                            className="remove-dest-btn"
                            onClick={() => handleRemoveDestination(dest.id)}
                            title="Удалить город"
                          >
                            ×
                          </button>
                        )}
                      </div>
                      <div className="form-field">
                        <CitySelect
                          value={dest.city}
                          onSelect={(val) => updateDestination(dest.id, "city", val)}
                          lang={lang}
                        />
                      </div>
                      <div className="form-field">
                        <DateRangePicker
                          value={dest.dates}
                          onChange={(val) => updateDestination(dest.id, "dates", val)}
                          lang={lang}
                        />
                      </div>
                      {index < destinations.length - 1 && <div className="destination-divider">↓</div>}
                    </div>
                  ))}

                  <div className="form-actions">
                    <button className="add-city-btn" onClick={handleAddDestination}>
                      {t.addCity}
                    </button>
                  </div>
                  {/* Options */}
                  {/* Transport Selection */}
                  <div className="trip-type-selector">
                    <label className="section-label">Транспорт:</label>
                    <div className="trip-types">
                      {[
                        { id: "plane", label: t.plane },
                        { id: "train", label: t.train },
                        { id: "car", label: t.car },
                        { id: "bus", label: t.bus },
                      ].map(type => (
                        <div
                          key={type.id}
                          className={`trip-type-chip ${options.transport === type.id ? "active" : ""}`}
                          onClick={() => setOptions({ ...options, transport: type.id })}
                        >
                          {type.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Gender Selection */}
                  <div className="trip-type-selector">
                    <label className="section-label">Пол:</label>
                    <div className="trip-types">
                      {[
                        { id: "unisex", label: t.unisex },
                        { id: "male", label: t.male },
                        { id: "female", label: t.female },
                      ].map(type => (
                        <div
                          key={type.id}
                          className={`trip-type-chip ${options.gender === type.id ? "active" : ""}`}
                          onClick={() => setOptions({ ...options, gender: type.id })}
                        >
                          {type.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="trip-type-selector">
                    <label className="section-label">Тип поездки:</label>
                    <div className="trip-types">
                      {[
                        { id: "vacation", label: t.vacation },
                        { id: "business", label: t.business },
                        { id: "active", label: t.active },
                        { id: "beach", label: t.beach },
                        { id: "winter", label: t.winter },
                      ].map(type => (
                        <div
                          key={type.id}
                          className={`trip-type-chip ${options.trip_type === type.id ? "active" : ""}`}
                          onClick={() => setOptions({ ...options, trip_type: type.id })}
                        >
                          {type.label}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="options-grid">
                    <label className={`option-chip ${options.traveling_with_pet ? "active" : ""}`}>
                      <input
                        type="checkbox"
                        checked={options.traveling_with_pet}
                        onChange={e => setOptions({ ...options, traveling_with_pet: e.target.checked })}
                      />
                      {t.pet}
                    </label>
                    <label className={`option-chip ${options.has_allergies ? "active" : ""}`}>
                      <input
                        type="checkbox"
                        checked={options.has_allergies}
                        onChange={e => setOptions({ ...options, has_allergies: e.target.checked })}
                      />
                      {t.allergies}
                    </label>
                    <label className={`option-chip ${options.has_chronic_diseases ? "active" : ""}`}>
                      <input
                        type="checkbox"
                        checked={options.has_chronic_diseases}
                        onChange={e => setOptions({ ...options, has_chronic_diseases: e.target.checked })}
                      />
                      {t.meds}
                    </label>
                  </div>

                  <div className="form-field generate-field">
                    <button
                      className="generate-btn"
                      onClick={handleSubmit}
                      disabled={false}
                    >
                      ✨ {t.generate}
                    </button>
                  </div>
                </div>
              </>
            )}

            {error && <div className="error-message">{error}</div>}

            {result && (
              <div className="results-section">
                <h2>
                  <h2>
                    <span>{result.city}</span>
                    <span className="checklist-dates">
                      {new Date(result.start_date || destinations[0].dates.start).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long' })}
                      {" — "}
                      {new Date(result.end_date || destinations[destinations.length - 1].dates.end).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long' })}
                    </span>
                  </h2>

                </h2>

                {/* Если это мульти-город, показываем маршрут визуально? Пока просто заголовок */}
                <div className="checklist-card">
                  {(() => {
                    const isMobile = window.innerWidth <= 600;
                    const isTablet = window.innerWidth > 600 && window.innerWidth <= 900;
                    let items = (result.items || []).filter(item => !removedItems.includes(item));
                    let columns = 3;
                    if (isTablet) columns = 2;
                    if (isMobile) columns = 1;
                    const perCol = Math.ceil(items.length / columns);
                    const cols = Array.from({ length: columns }, (_, i) => items.slice(i * perCol, (i + 1) * perCol));
                    return (
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
                                    title="Удалить"
                                    onClick={e => { e.preventDefault(); handleRemoveItem(item); }}
                                    tabIndex={-1}
                                  >×</button>
                                </label>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}

                  <div className="checklist-actions">
                    <button className="action-btn" onClick={resetChecklist}>Сбросить отметки</button>
                    <button className="action-btn" onClick={() => setAddItemMode(v => !v)}>
                      {addItemMode ? "Отмена" : "+ Добавить вещь"}
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
                        />
                        <button className="action-btn primary" onClick={handleAddItem}>OK</button>
                      </>
                    )}
                    {removedItems.length > 0 && (
                      <button className="action-btn" onClick={handleRestoreAll}>
                        Восстановить удалённые
                      </button>
                    )}
                  </div>
                </div>

                {/* Weather Forecast */}
                <div className="forecast">
                  <h3>🌤 <span>{t.forecast}</span></h3>
                  <div className="forecast-grid">
                    {result.daily_forecast.map((day) => (
                      <div key={day.date} className={`forecast-card${day.source === "historical" ? " forecast-historical" : ""}`}>
                        <div className="forecast-date">{formatDate(day.date)}</div>

                        <img
                          src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                          alt={day.condition}
                          className="forecast-icon"
                        />
                        <div className="forecast-conditions">{day.condition}</div>
                        <div className="forecast-temp">
                          {day.temp_min.toFixed(1)}° / {day.temp_max.toFixed(1)}°C
                        </div>
                        <div className="forecast-details">
                          {day.humidity !== null && <span title="Влажность">💧 {day.humidity}%</span>}
                          {day.uv_index !== null && <span title="УФ-индекс">☀️ {day.uv_index.toFixed(0)}</span>}
                          {day.wind_speed !== null && <span title="Ветер">💨 {day.wind_speed.toFixed(0)} км/ч</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            )}
          </>
        )}
      </div>
    </>
  );
};

export default App;

