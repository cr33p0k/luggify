import React, { useState, useEffect } from "react";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";

import "./App.css";

function App() {
  const [city, setCity] = useState(null);
  const [dates, setDates] = useState({ start: null, end: null });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");
  const [tgUser, setTgUser] = useState(null);
  const [isTg, setIsTg] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line no-undef
    const tg = window.Telegram?.WebApp;
    if (tg) {
      setIsTg(true);
      tg.ready();
      if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        setTgUser(tg.initDataUnsafe.user);
      }
    }
  }, []);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    if (!city || !dates.start || !dates.end) {
      alert("Заполните все поля!");
      return;
    }
    try {
      const res = await fetch("https://luggify.vercel.app/generate-packing-list", {
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

  return (
    <div className="container">
      <h1>Luggify TMA</h1>
      {isTg && tgUser && (
        <div className="tg-user">Привет, {tgUser.first_name}!</div>
      )}
      <CitySelect value={city} onSelect={setCity} />
      <DateRangePicker onChange={setDates} />
      <button onClick={handleSubmit}>Сгенерировать список</button>
      {error && <div className="error">{error}</div>}
      {result && (
        <ul>
          {result.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default App;
