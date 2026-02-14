import React from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "./DateRangePicker.css";

const TRANSLATIONS = {
  ru: {
    label: "Даты поездки",
    start: "Начало",
    end: "Конец",
  },
  en: {
    label: "Trip Dates",
    start: "Start",
    end: "End",
  }
};

const DateRangePicker = ({ value, onChange, lang = "ru" }) => {
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  // value expected to be { start: "YYYY-MM-DD", end: "YYYY-MM-DD" }

  const handleStart = (date) => {
    onChange({
      ...value,
      start: date ? date.toISOString().split("T")[0] : null,
    });
  };

  const handleEnd = (date) => {
    onChange({
      ...value,
      end: date ? date.toISOString().split("T")[0] : null,
    });
  };

  const startDate = value?.start ? new Date(value.start) : null;
  const endDate = value?.end ? new Date(value.end) : null;

  return (
    <div className="input-group">
      <label>{t.label}</label>
      <div className="date-row">
        <div className="date-field">
          <DatePicker
            selected={startDate}
            onChange={handleStart}
            dateFormat="dd.MM.yyyy"
            placeholderText={t.start}
            className="date-input"
            minDate={new Date()}
          />
        </div>
        <div className="date-field">
          <DatePicker
            selected={endDate}
            onChange={handleEnd}
            dateFormat="dd.MM.yyyy"
            placeholderText={t.end}
            className="date-input"
            minDate={startDate || new Date()}
          />
        </div>
      </div>
    </div>
  );
};

export default DateRangePicker;
