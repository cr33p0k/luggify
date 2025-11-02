import React from "react";
import AsyncSelect from "react-select/async";
import "./CitySelect.css";


const fetchCitiesWithCountry = async (inputValue) => {
  if (!inputValue || inputValue.length < 2) return [];
  try {
    const res = await fetch(`https://luggify.onrender.com/geo/cities-autocomplete?namePrefix=${inputValue}`);
    if (!res.ok) {
      console.error("Ошибка при загрузке городов:", res.status, res.statusText);
      return [];
    }
    const data = await res.json();
    if (!Array.isArray(data)) {
      console.error("Неверный формат данных от сервера");
      return [];
    }
    return data.map((city) => ({
      label: city.fullName,
      value: city,
    }));
  } catch (e) {
    console.error("Ошибка при загрузке городов:", e);
    return [];
  }
};

const CitySelect = ({ onSelect }) => (
  <div className="input-group">
    <label>Город</label>
    <AsyncSelect
      classNamePrefix="react-select"
      cacheOptions
      loadOptions={fetchCitiesWithCountry}
      defaultOptions
      onChange={(option) => onSelect(option ? option.value : null)}
      placeholder="Введите город"
      noOptionsMessage={() => "Город не найден"}
      isClearable
    />
  </div>
);

export default CitySelect;
