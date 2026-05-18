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
  <svg {...iconProps} {...props}><path d="m10.5 13.5-7-2.5 1.1-2.2 7.8 1.2L18 4.4a2.6 2.6 0 0 1 3.7 0 2.6 2.6 0 0 1 0 3.7L16 13.8l1.2 7.8-2.2 1.1-2.5-7-3.6 3.6v3.2l-1.8 1-1.2-3.2-3.2-1.2 1-1.8h3.2z" /></svg>
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

export const CityTripIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M3 21h18" /><path d="M5 21V9l4-3v15" /><path d="M9 21V4l6 2v15" /><path d="M15 21v-9l4 2v7" /><path d="M11 8h2" /><path d="M11 12h2" /><path d="M11 16h2" /><path d="M6 12h1" /><path d="M6 16h1" /></svg>
);
export const VacationIcon = CityTripIcon;

export const BusinessTripIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="18" height="12" x="3" y="8" rx="2" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /><path d="M3 13h18" /><path d="M10 13v2" /><path d="M14 13v2" /></svg>
);
export const BusinessIcon = BusinessTripIcon;

export const OutdoorTripIcon = (props) => (
  <svg {...iconProps} {...props}><path d="m3 20 6-9 4 5 3-4 5 8" /><path d="m7 20 5-8 3 4" /><path d="M15 5h4" /><path d="M17 3v4" /></svg>
);
export const ActiveIcon = OutdoorTripIcon;

export const BeachTripIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M4 20c1.5-1 3-1 4.5 0s3 1 4.5 0 3-1 4.5 0 3 1 4.5 0" /><path d="M12 4v9" /><path d="M12 4a4 4 0 0 0-4 4h8a4 4 0 0 0-4-4Z" /><path d="M12 13l-2 7" /></svg>
);
export const BeachIcon = BeachTripIcon;

export const WinterTripIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 2v20" /><path d="m7 5 5 3 5-3" /><path d="m7 19 5-3 5 3" /><path d="M2 12h20" /><path d="m5 7 3 5-3 5" /><path d="m19 7-3 5 3 5" /></svg>
);
export const WinterIcon = WinterTripIcon;

export const FamilyTripIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="8" cy="7" r="2" /><circle cx="16" cy="7" r="2" /><circle cx="12" cy="11" r="1.5" /><path d="M5 20v-3a3 3 0 0 1 3-3h0a3 3 0 0 1 3 3v3" /><path d="M13 20v-3a3 3 0 0 1 3-3h0a3 3 0 0 1 3 3v3" /><path d="M10 20v-2a2 2 0 0 1 4 0v2" /></svg>
);

export const RomanticTripIcon = (props) => (
  <svg {...iconProps} {...props}><path d="m12 20-1.4-1.3C5.4 13.8 3 11.6 3 8.8A4.3 4.3 0 0 1 7.3 4.5c1.6 0 3.1.8 4 2.1.9-1.3 2.4-2.1 4-2.1A4.3 4.3 0 0 1 19.6 8.8c0 2.8-2.4 5-7.6 9.9L12 20Z" /></svg>
);

export const CalendarIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="18" height="18" x="3" y="4" rx="2" ry="2" /><line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" /><line x1="3" x2="21" y1="10" y2="10" /></svg>
);

export const SparkleIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" /></svg>
);

export const SunIcon = (props) => (
  <svg {...iconProps} {...props}>
    <circle cx="12" cy="12" r="4.5" />
    <path d="M12 2.5v2.5" />
    <path d="M12 19v2.5" />
    <path d="m4.9 4.9 1.8 1.8" />
    <path d="m17.3 17.3 1.8 1.8" />
    <path d="M2.5 12H5" />
    <path d="M19 12h2.5" />
    <path d="m4.9 19.1 1.8-1.8" />
    <path d="m17.3 6.7 1.8-1.8" />
  </svg>
);

export const MoonIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M20.2 14.2A8.5 8.5 0 1 1 9.8 3.8a7 7 0 1 0 10.4 10.4Z" />
  </svg>
);

export const WeatherIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" /></svg>
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

export const CheckCircleIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
);

export const XCricleIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="10" /><line x1="15" x2="9" y1="9" y2="15" /><line x1="9" x2="15" y1="9" y2="15" /></svg>
);

export const TrophyIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" /><path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" /><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" /><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" /></svg>
);

export const ListIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="8" x2="21" y1="6" y2="6" /><line x1="8" x2="21" y1="12" y2="12" /><line x1="8" x2="21" y1="18" y2="18" /><line x1="3" x2="3.01" y1="6" y2="6" /><line x1="3" x2="3.01" y1="12" y2="12" /><line x1="3" x2="3.01" y1="18" y2="18" /></svg>
);

export const BarChartIcon = (props) => (
  <svg {...iconProps} {...props}><line x1="12" x2="12" y1="20" y2="10" /><line x1="18" x2="18" y1="20" y2="4" /><line x1="6" x2="6" y1="20" y2="16" /></svg>
);
export const EditIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M12 20h9" /><path d="m16.5 3.5 4 4L8 20l-5 1 1-5Z" /></svg>
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
export const BackpackIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M7 8V6a5 5 0 0 1 10 0v2" /><path d="M6 8h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v-8a3 3 0 0 1 3-3Z" /><path d="M9 8h6" /><path d="M9 13h6" /><path d="M10 13v3a2 2 0 0 0 4 0v-3" /></svg>
);
export const SuitcaseIcon = (props) => (
  <svg {...iconProps} {...props}><rect x="4" y="7" width="16" height="13" rx="2" /><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" /><path d="M4 12h16" /><path d="M12 12v3" /></svg>
);
export const HotelIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M4 21V7a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v14" /><path d="M16 10h2a2 2 0 0 1 2 2v9" /><path d="M8 9h2" /><path d="M8 13h2" /><path d="M8 17h2" /><path d="M12 9h2" /><path d="M12 13h2" /><path d="M12 17h2" /><path d="M4 21h16" /><path d="M10 21v-3a2 2 0 0 1 4 0v3" /></svg>
);
export const MuseumIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M3 21h18" /><path d="M4 8h16" /><path d="M6 21V10" /><path d="M10 21V10" /><path d="M14 21V10" /><path d="M18 21V10" /><path d="m12 3 8 5H4Z" /></svg>
);
export const SmartphoneIcon = (props) => (
  <svg {...iconProps} {...props}><rect width="14" height="20" x="5" y="2" rx="3" ry="3" /><path d="M9 6h6" /><path d="M12 18h.01" /></svg>
);
export const GlobeIcon = (props) => (
  <svg {...iconProps} {...props}><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a13 13 0 0 1 0 18" /><path d="M12 3a13 13 0 0 0 0 18" /></svg>
);

export const MapIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M14.5 18.5 9.5 16 3 19.5V5.5L9.5 2l5 2.5L21 1v14l-6.5 3.5Z" /><path d="M9.5 2v14" /><path d="M14.5 4.5v14" /></svg>
);

export const WalletIcon = (props) => (
  <svg {...iconProps} {...props}><path d="M19 7V5.5A2.5 2.5 0 0 0 16.5 3h-11A2.5 2.5 0 0 0 3 5.5v13A2.5 2.5 0 0 0 5.5 21h13A2.5 2.5 0 0 0 21 18.5V10a2 2 0 0 0-2-2H7" /><path d="M3 6.5h13" /><path d="M17 14h.01" /></svg>
);

export const UsersIcon = (props) => (
  <svg {...iconProps} {...props}>
    <path d="M16 21v-1.2a3.8 3.8 0 0 0-3.8-3.8H8.8A3.8 3.8 0 0 0 5 19.8V21" />
    <circle cx="10.5" cy="8.5" r="3.5" />
    <path d="M19 21v-1a3.2 3.2 0 0 0-2.4-3.1" />
    <path d="M15.8 5.4a3.2 3.2 0 0 1 0 6.2" />
  </svg>
);
