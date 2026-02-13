import React from "react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "./DateRangePicker.css";

const DateRangePicker = ({ onChange }) => {
  const [startDate, setStartDate] = React.useState(null);
  const [endDate, setEndDate] = React.useState(null);

  const handleStart = (date) => {
    setStartDate(date);
    if (date) {
      onChange((d) => ({
        ...d,
        start: date.toISOString().split("T")[0],
      }));
    }
  };

  const handleEnd = (date) => {
    setEndDate(date);
    if (date) {
      onChange((d) => ({
        ...d,
        end: date.toISOString().split("T")[0],
      }));
    }
  };

  return (
    <div className="input-group">
      <label>Даты поездки</label>
      <div className="date-row">
        <div className="date-field">
          <DatePicker
            selected={startDate}
            onChange={handleStart}
            dateFormat="dd.MM.yyyy"
            placeholderText="Начало"
            className="date-input"
            minDate={new Date()}
          />
        </div>
        <div className="date-field">
          <DatePicker
            selected={endDate}
            onChange={handleEnd}
            dateFormat="dd.MM.yyyy"
            placeholderText="Конец"
            className="date-input"
            minDate={startDate || new Date()}
          />
        </div>
      </div>
    </div>
  );
};

export default DateRangePicker;
