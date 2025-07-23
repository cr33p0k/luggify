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
  const [columns, setColumns] = useState(3);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showChecklists, setShowChecklists] = useState(false);
  const [myChecklists, setMyChecklists] = useState([]);
  const [checklistsLoading, setChecklistsLoading] = useState(false);

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

  // Удалён useEffect, который автоматически подгружал чеклист по tg_user_id при старте

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 700) setColumns(1);
      else if (window.innerWidth <= 1100) setColumns(2);
      else setColumns(3);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    if (!city || !dates.start || !dates.end) {
      alert("Заполните все поля!");
      return;
    }
    setLoading(true);
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
        setLoading(false);
        return;
      }
      const data = await res.json();
      setResult(data);
      // Сохраняем чеклист для Telegram пользователя
      if (isTg && tgUser && tgUser.id) {
        setSaving(true);
        fetch("https://luggify.onrender.com/save-tg-checklist", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            city: data.city,
            start_date: data.start_date,
            end_date: data.end_date,
            items: data.items,
            avg_temp: data.avg_temp,
            conditions: data.conditions,
            tg_user_id: String(tgUser.id),
          }),
        })
          .then(() => setSaving(false))
          .catch(() => setSaving(false));
      }
    } catch (e) {
      setError("Ошибка при запросе к серверу");
    } finally {
      setLoading(false);
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

  // Загрузка всех чеклистов пользователя
  const handleShowChecklists = async () => {
    if (!tgUser || !tgUser.id) return;
    setChecklistsLoading(true);
    setShowChecklists(true);
    setError(null);
    try {
      const res = await fetch(`https://luggify.onrender.com/tg-checklists/${String(tgUser.id)}`);
      if (!res.ok) {
        setError("Ошибка при загрузке чеклистов");
        setMyChecklists([]);
      } else {
        const data = await res.json();
        setMyChecklists(data);
      }
    } catch {
      setError("Ошибка при загрузке чеклистов");
      setMyChecklists([]);
    } finally {
      setChecklistsLoading(false);
    }
  };

  // Открыть выбранный чеклист
  const handleOpenChecklist = async (checklist) => {
    setResult(checklist);
    setShowChecklists(false);
    // Подгружаем актуальный прогноз погоды
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("https://luggify.onrender.com/generate-packing-list", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: checklist.city,
          start_date: checklist.start_date,
          end_date: checklist.end_date,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(prev => prev ? { ...prev, daily_forecast: data.daily_forecast } : prev);
      }
    } catch {
      // Не показываем ошибку, если не удалось получить прогноз
    } finally {
      setLoading(false);
    }
  };

  // Сохранить текущий чеклист в мои чеклисты
  const handleSaveChecklist = async () => {
    if (!result || !tgUser || !tgUser.id) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("https://luggify.onrender.com/save-tg-checklist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          city: result.city,
          start_date: result.start_date,
          end_date: result.end_date,
          items: result.items,
          avg_temp: result.avg_temp,
          conditions: result.conditions,
          tg_user_id: String(tgUser.id),
        }),
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 1500);
      } else {
        setError("Ошибка при сохранении чеклиста");
      }
    } catch {
      setError("Ошибка при сохранении чеклиста");
    } finally {
      setSaving(false);
    }
  };

  // Добавляю функцию для удаления чеклиста
  const handleDeleteChecklist = async (slug) => {
    if (!tgUser || !tgUser.id) return;
    setChecklistsLoading(true);
    setError(null);
    try {
      const res = await fetch(`https://luggify.onrender.com/checklist/${slug}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setMyChecklists((prev) => prev.filter((cl) => cl.slug !== slug));
      } else {
        setError('Ошибка при удалении чеклиста');
      }
    } catch {
      setError('Ошибка при удалении чеклиста');
    } finally {
      setChecklistsLoading(false);
    }
  };

  return (
    <div className={`container large ${result ? "expanded" : ""}`}
      style={{ maxWidth: 600, margin: "0 auto", padding: 16 }}>
      <h1 style={{ textAlign: "center", marginBottom: 12 }}>Luggify</h1>
      {isTg && tgUser && (
        <div className="tg-user">Привет, {tgUser.first_name}!</div>
      )}
      {error && <div className="error">{error}</div>}
      {saveSuccess && <div style={{ color: 'orange', textAlign: 'center', marginBottom: 8 }}>Сохранено!</div>}
      {/* Форма генерации и кнопка мои чеклисты */}
      {!result && !loading && !showChecklists && (
        <>
          <div className="input-group">
            <CitySelect value={city} onSelect={setCity} />
          </div>
          <DateRangePicker onChange={setDates} />
          <button className="main-btn" onClick={handleSubmit} style={{ width: "100%", marginTop: 12 }}>Сгенерировать список</button>
          {isTg && tgUser && (
            <button className="main-btn" style={{ width: "100%", marginTop: 8, background: '#444', color: 'orange', border: '1.5px solid orange' }} onClick={handleShowChecklists}>
              Мои чеклисты
            </button>
          )}
        </>
      )}
      {/* Список чеклистов пользователя */}
      {showChecklists && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ color: 'orange', marginBottom: 12, textAlign: 'center' }}>Мои чеклисты</h2>
          {checklistsLoading ? null : myChecklists.length === 0 ? (
            <div style={{ color: '#ccc', textAlign: 'center' }}>Нет сохранённых чеклистов</div>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {myChecklists.map((cl) => (
                <li key={cl.slug} style={{ position: 'relative', marginBottom: 12, background: '#222', borderRadius: 8, padding: 12, boxShadow: '0 0 8px #ffae4222' }}>
                  <div style={{ fontWeight: 600, color: 'orange' }}>{cl.city}</div>
                  <div style={{ fontSize: 13, color: '#aaa' }}>{cl.start_date} — {cl.end_date}</div>
                  <button className="main-btn" style={{ marginTop: 8, width: '100%' }} onClick={() => handleOpenChecklist(cl)}>
                    Открыть
                  </button>
                  <button
                    style={{
                      position: 'absolute',
                      top: 8,
                      right: 8,
                      background: 'none',
                      border: 'none',
                      color: '#ff4d00',
                      fontSize: 22,
                      cursor: 'pointer',
                      padding: 0,
                      lineHeight: 1,
                    }}
                    title="Удалить чеклист"
                    onClick={() => handleDeleteChecklist(cl.slug)}
                    disabled={checklistsLoading}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button className="main-btn" style={{ width: '100%', marginTop: 8, background: '#444', color: 'orange', border: '1.5px solid orange' }} onClick={() => setShowChecklists(false)}>
            Назад
          </button>
        </div>
      )}
      {/* Чеклист */}
      {result && !loading && !showChecklists && (
        <div className="result">
          {/* Чеклист */}
          {(() => {
            let items = (result.items || []).filter(item => !removedItems.includes(item));
            let colCount = columns;
            if (window.innerWidth <= 700) colCount = 1;
            const perCol = Math.ceil(items.length / colCount);
            const cols = Array.from({ length: colCount }, (_, i) => items.slice(i * perCol, (i + 1) * perCol));
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
          {/* Кнопка сохранить чеклист перенесена вниз */}
          {isTg && tgUser && (
            <button className="main-btn" style={{ width: '100%', marginTop: 24, background: '#444', color: 'orange', border: '1.5px solid orange' }} onClick={handleSaveChecklist} disabled={saving}>
              Сохранить в мои чеклисты
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
