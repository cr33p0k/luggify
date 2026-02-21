import React from "react";
import AsyncSelect from "react-select/async";
import "./CitySelect.css";


const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const fetchCitiesWithCountry = async (inputValue) => {
  if (!inputValue || inputValue.length < 2) return [];
  try {
    const res = await fetch(`${API_URL}/geo/cities-autocomplete?namePrefix=${encodeURIComponent(inputValue)}`);
    const data = await res.json();
    return data.map((city) => ({
      label: city.fullName,
      value: city,
    }));
  } catch (e) {
    console.error("Ошибка при загрузке городов:", e);
    return [];
  }
};

const TRANSLATIONS = {
  ru: {
    label: "Город",
    placeholder: "Начните вводить город...",
    notFound: "Город не найден",
    loading: "Поиск...",
  },
  en: {
    label: "City",
    placeholder: "Start typing city...",
    notFound: "City not found",
    loading: "Searching...",
  }
};

const CitySelect = ({ value, onSelect, lang = "ru", label }) => {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;

  return (
    <div className="input-group">
      <label>{label || t.label}</label>
      <AsyncSelect
        classNamePrefix="react-select"
        cacheOptions
        loadOptions={fetchCitiesWithCountry}
        onChange={(option) => onSelect(option ? option.value : null)}
        value={value ? { label: value.label || value.fullName, value: value } : null}
        placeholder={t.placeholder}
        noOptionsMessage={() => t.notFound}
        loadingMessage={() => t.loading}
        isClearable
        menuPlacement="auto"
      />
    </div>
  );
};

export default CitySelect;
