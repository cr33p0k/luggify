import React from "react";
import AsyncSelect from "react-select/async";
import "./CitySelect.css";


const fetchCitiesWithCountry = async (inputValue) => {
  if (!inputValue) return [];
  try {
    const res = await fetch(`http://localhost:8000/geo/cities-autocomplete?namePrefix=${inputValue}`);
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
