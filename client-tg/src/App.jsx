import React, { useState, useEffect } from "react";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";
import "./App.css";

function App() {
  const [city, setCity] = useState(null);
  const [dates, setDates] = useState({ start: null, end: null });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [checkedItems, setCheckedItems] = useState({});
  const [removedItems, setRemovedItems] = useState([]);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");
  const [tgUser, setTgUser] = useState(null);
  const [isTg, setIsTg] = useState(false);

  useEffect(() => {
    // Telegram WebApp API
    const tg = window.Telegram?.WebApp;
    if (tg) {
      setIsTg(true);
      tg.ready();
      if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        setTgUser(tg.initDataUnsafe.user);
      }
    }
  }, []);

  useEffect(() => {
    if (result && result.items) {
      // Сбросить чекбоксы при новом списке
      const initial = {};
      result.items.forEach(item => {
        initial[item] = false;
      });
      setCheckedItems(initial);
      setRemovedItems([]);
    }
  }, [result]);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    if (!city || !dates.start || !dates.end) {
      alert("Заполните все поля!");
      return;
    }
    try {
      const res = await fetch("https://luggify.onrender.com/generate-packing-list", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: city.fullName || city,
          start_date: dates.start,
          end_date: dates.end,
        }),
      });
      if (!res.ok) {
        setError("Ошибка при генерации списка");
        return;
      }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError("Ошибка при запросе к серверу");
    }
  };

  const handleCheck = (item) => {
    setCheckedItems(prev => ({ ...prev, [item]: !prev[item] }));
  };

  const handleRemoveItem = (item) => {
    setRemovedItems(prev => [...prev, item]);
  };

  const handleRestoreAll = () => {
    setRemovedItems([]);
  };

  const resetChecklist = () => {
    if (!result || !result.items) return;
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
    <div className={`container large ${result ? "expanded" : ""}`}
      style={{ maxWidth: 600, margin: "0 auto", padding: 16 }}>
      <h1 style={{ textAlign: "center", marginBottom: 12 }}>Luggify</h1>
      {isTg && tgUser && (
        <div className="tg-user">Привет, {tgUser.first_name}!</div>
      )}
      {!result && (
        <>
          <div className="input-group">
            <CitySelect value={city} onSelect={setCity} />
          </div>
          <DateRangePicker onChange={setDates} />
          <button className="main-btn" onClick={handleSubmit} style={{ width: "100%", marginTop: 12 }}>Сгенерировать список</button>
        </>
      )}
      {error && <div className="error">{error}</div>}
      {result && (
        <div className="result">
          {/* Чеклист */}
          {(() => {
            let items = (result.items || []).filter(item => !removedItems.includes(item));
            const isMobile = window.innerWidth <= 700;
            const columns = isMobile ? 1 : 2;
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
            );
          })()}
          {/* Кнопки управления чеклистом */}
          <div className="checklist-actions" style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
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
          {/* Прогноз погоды */}
          {result.daily_forecast && (
            <div className="forecast" style={{ marginTop: 24 }}>
              <h3 style={{ marginBottom: 8 }}>Прогноз погоды</h3>
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
        </div>
      )}
    </div>
  );
}

export default App;
