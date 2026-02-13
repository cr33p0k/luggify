import React, { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";
import AuthModal from "./AuthModal";
import ProfilePage from "./ProfilePage";

import "./App.css";
import "./AuthModal.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const App = ({ page }) => {
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

    // Без ограничения по дням — сервер использует прогноз + исторические данные

    try {
      const res = await fetch(`${API_URL}/generate-packing-list`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          city: city.fullName,
          start_date: dates.start,
          end_date: dates.end,
        }),
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
                title="Выйти"
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
            <button className="navbar-login-btn" onClick={() => setShowAuth(true)}>Войти</button>
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
                  <h2>Куда собираемся?</h2>
                  <p>Введите город и даты — мы соберём идеальный чеклист для вашей поездки</p>
                </div>

                <div className="form-card">
                  <div className="form-field">
                    <CitySelect value={city} onSelect={setCity} />
                  </div>
                  <div className="form-field">
                    <DateRangePicker onChange={(newDates) => setDates(newDates)} />
                  </div>
                  <button className="generate-btn" onClick={handleSubmit}>
                    Сгенерировать ✨
                  </button>
                </div>
              </>
            )}

            {error && <div className="error-message">{error}</div>}

            {result && (
              <div className="results-section">
                <h2>
                  <span>{(result.city || city?.fullName).split(",")[0]}</span>
                  <span className="checklist-dates">
                    {new Date(result.start_date || dates.start).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long' })}
                    {" — "}
                    {new Date(result.end_date || dates.end).toLocaleDateString("ru-RU", { day: 'numeric', month: 'long' })}
                  </span>
                </h2>

                {/* Checklist Card */}
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
                  <h3>🌤 <span>Прогноз погоды</span></h3>
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

