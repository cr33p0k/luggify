import React from 'react';

// Common SVG props
const iconProps = {
  xmlns: "http://www.w3.org/2000/svg",
  width: "20",
  height: "20",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: "2",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  style: { display: 'inline-block', verticalAlign: 'middle', marginRight: '6px' }
};

export const PlaneIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.2-1.1.6L3 8l6 4-3 3-3.6-.6c-.4 0-.8.3-.9.7L1 16l3.4 1 1 3.4.9-.5c.4-.1.7-.5.7-.9L6 16l3-3 4 6l1.2-.7c.4-.2.7-.6.6-1.1z" /></svg>
);

export const TrainIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="16" height="16" x="4" y="3" rx="2" /><path d="M4 11h16" /><path d="M12 3v8" /><path d="m8 19-2 3" /><path d="m18 22-2-3" /><path d="M8 15h0" /><path d="M16 15h0" /></svg>
);

export const CarIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" /><circle cx="7" cy="17" r="2" /><path d="M9 17h6" /><circle cx="17" cy="17" r="2" /></svg>
);

export const BusIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M8 6v6" /><path d="M15 6v6" /><path d="M2 12h19.6" /><path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3" /><circle cx="7" cy="18" r="2" /><path d="M9 18h5" /><circle cx="16" cy="18" r="2" /></svg>
);

export const MaleIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="10" cy="14" r="5" /><path d="M14 10.5 21 3.5" /><path d="M16 3h5v5" /></svg>
);

export const FemaleIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="10" r="5" /><path d="M12 15v7" /><path d="M9 19h6" /></svg>
);

export const UnisexIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="4" /><path d="M12 8V3" /><path d="M10 5h4" /><path d="m15.5 15.5 3.5 3.5" /><path d="m15 19 4 4" /><path d="m19 15 4 4" /></svg>
);

export const VacationIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 3v1" /><path d="M18.4 6.6l-.7.7" /><path d="M21 13h-1" /><path d="M18.4 19.4l-.7-.7" /><path d="M12 21v-1" /><path d="M5.6 19.4l.7-.7" /><path d="M3 13h1" /><path d="M5.6 6.6l.7.7" /><circle cx="12" cy="12" r="4" /></svg>
);

export const BusinessIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="20" height="14" x="2" y="7" rx="2" ry="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></svg>
);

export const ActiveIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M7 16l4-4v-4" /><path d="M11 8h4l2 4" /><circle cx="11" cy="4" r="2" /><path d="M11 12l-4 4-2-2" /><path d="M15 12l4 4-2 2" /></svg>
);

export const BeachIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 2v20" /><path d="M2 12h20" /><path d="m4.9 4.9 14.2 14.2" /><path d="m4.9 19.1 14.2-14.2" /></svg>
);

export const WinterIcon = (props) => (
  <svg {...iconProps} {...props}><path d="m10 20-3-3 3-3" /><path d="M7 17h10" /><path d="m14 14 3 3-3 3" /></svg>
);

export const PetIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 11a4 4 0 1 0-4 4h8a4 4 0 1 0-4-4z" /><circle cx="7.5" cy="5.5" r="1.5" /><circle cx="16.5" cy="5.5" r="1.5" /><circle cx="3.5" cy="10.5" r="1.5" /><circle cx="20.5" cy="10.5" r="1.5" /></svg>
);

export const AllergyIcon = (props) => (
  <svg {...iconProps} {...props}><path d="m12 14 4-4" /><path d="M3.3 17a3 3 0 1 0 4.2-4.2L3 8V3h5l4.8 4.5a3 3 0 0 0 4.2 4.2l3-3V3h-5l-4.5 4.8" /></svg>
);

export const MedsIcon = (props) => (
  <svg {...iconProps} {...props}><path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" /><path d="m8.5 8.5 7 7" /></svg>
);

export const CalendarIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="18" height="18" x="3" y="4" rx="2" ry="2" /><line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" /><line x1="3" x2="21" y1="10" y2="10" /></svg>
);

export const PrintIcon = (props) => (
  <svg {...iconProps} {...props}><polyline points="6 9 6 2 18 2 18 9" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect width="12" height="8" x="6" y="14" /></svg>
);

export const SparkleIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" /></svg>
);

export const WeatherIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" /></svg>
);

export const UVIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></svg>
);

export const EyeIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>
);

export const LockIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
);

export const UnlockIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 9.9-1" /></svg>
);

export const CheckIcon = (props) => (
  <svg {...iconProps} {...props}><polyline points="20 6 9 17 4 12" /></svg>
);

export const XIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="18" x2="6" y1="6" y2="18" /><line x1="6" x2="18" y1="6" y2="18" /></svg>
);

export const CheckCircleIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
);

export const XCricleIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="10" /><line x1="15" x2="9" y1="9" y2="15" /><line x1="9" x2="15" y1="9" y2="15" /></svg>
);

export const BuildingIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="16" height="20" x="4" y="2" rx="2" ry="2" /><path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" /><path d="M12 6h.01" /><path d="M12 10h.01" /><path d="M12 14h.01" /><path d="M16 10h.01" /><path d="M16 14h.01" /><path d="M8 10h.01" /><path d="M8 14h.01" /></svg>
);

export const TrophyIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" /><path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" /><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" /><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" /></svg>
);

export const ListIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="8" x2="21" y1="6" y2="6" /><line x1="8" x2="21" y1="12" y2="12" /><line x1="8" x2="21" y1="18" y2="18" /><line x1="3" x2="3.01" y1="6" y2="6" /><line x1="3" x2="3.01" y1="12" y2="12" /><line x1="3" x2="3.01" y1="18" y2="18" /></svg>
);

export const MapPinIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" /><circle cx="12" cy="10" r="3" /></svg>
);

export const BarChartIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="12" x2="12" y1="20" y2="10" /><line x1="18" x2="18" y1="20" y2="4" /><line x1="6" x2="6" y1="20" y2="16" /></svg>
);
export const ClockIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
);
export const DropletIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" /></svg>
);
export const WindIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" /><path d="M9.6 4.6A2 2 0 1 1 11 8H2" /><path d="M12.6 19.4A2 2 0 1 0 14 16H2" /></svg>
);
export const TentIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M19 20 10 4" /><path d="m5 20 9-16" /><path d="M3 20h18" /><path d="m12 15-3 5" /><path d="m12 15 3 5" /></svg>
);
export const BackpackIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M4 10a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" /><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" /><path d="M8 21v-5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v5" /><path d="M8 10h8" /><path d="M8 14h8" /></svg>
);
export const HotelIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M10 22v-6.57" /><path d="M14 22v-6.57" /><path d="M10 6.57v15.43" /><path d="M14 6.57v15.43" /><path d="M4 22V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14" /><path d="M8 22H4" /><path d="M20 22h-4" /><path d="M8 10h.01" /><path d="M16 10h.01" /><path d="M8 14h.01" /><path d="M16 14h.01" /><path d="M8 18h.01" /><path d="M16 18h.01" /></svg>
);
export const MuseumIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="3" x2="21" y1="22" y2="22" /><line x1="6" x2="6" y1="18" y2="11" /><line x1="10" x2="10" y1="18" y2="11" /><line x1="14" x2="14" y1="18" y2="11" /><line x1="18" x2="18" y1="18" y2="11" /><polygon points="12 2 20 7 4 7" /></svg>
);
export const SmartphoneIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" /></svg>
);
export const GlobeIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" /><path d="M2 12h20" /></svg>
);
