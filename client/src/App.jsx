import React, { Suspense, useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import "maplibre-gl/dist/maplibre-gl.css";
import CitySelect from "./CitySelect";
import DateRangePicker from "./DateRangePicker";
import AuthModal from "./AuthModal";
import NavbarUserSearch from "./NavbarUserSearch";
import ConfirmDialog from "./ConfirmDialog";
import {
  PlaneIcon, TrainIcon, CarIcon, BusIcon,
  CalendarIcon, SparkleIcon, WeatherIcon, LockIcon, UnlockIcon,
  ClockIcon, DropletIcon, WindIcon, BackpackIcon, HotelIcon, MuseumIcon, SmartphoneIcon, GlobeIcon,
  SunIcon, MoonIcon, ListIcon, MapIcon, WalletIcon
} from './Icons';
import { TRANSLATIONS, formatDuration, pluralize } from "./i18n";
import {
  API_URL,
  normalizeUserId,
  readJsonSafely,
  resolveInitialTheme,
  safeParseJson,
} from "./appUtils";
import {
  clearOfflineChecklistSnapshots,
  clearPendingChecklistSnapshot,
  isOfflineChecklistEditable,
  loadLastChecklistSnapshot,
  loadPendingChecklistSnapshot,
  saveLastChecklistSnapshot,
  savePendingChecklistSnapshot,
} from "./offlineChecklist";
import {
  getItemQuantity,
  getNormalizedPackedQuantityMap,
  getNormalizedQuantityMap,
  getPackedQuantity,
  normalizeItemKey,
  normalizePackedQuantityMap,
  normalizeQuantityMap,
  setItemQuantityInMap,
  setPackedQuantityInMap,
} from "./packingState";
import {
  buildChecklistItemTranslationEntry,
  cacheChecklistItemTranslation,
  detectItemTextLanguage,
  normalizeChecklistItemTranslations,
  requestChecklistItemTranslation,
  translateAirlineLabel,
  translateChecklistCategoryLabel,
  translateChecklistItemLabel,
  translateFlightTagLabel,
  translateKnownBaggageName,
  translatePlaceLabel,
  translateWeatherConditionLabel,
} from "./checklistLocalization";
import "./App.css";
import "./AuthModal.css";
import "./AIChatWidget.css";

const ProfilePage = React.lazy(() => import("./ProfilePage"));
const AIChatWidget = React.lazy(() => import("./AIChatWidget"));

const FORECAST_DESKTOP_CARD_WIDTH = 146;
const FORECAST_DESKTOP_GAP = 12;
const MAX_REVIEW_PHOTOS = 8;

const getForecastRowLayout = (count) => {
  const safeCount = Math.max(1, Number(count) || 1);
  if (safeCount <= 7) return [safeCount];
  if (safeCount === 8) return [4, 4];
  if (safeCount === 9) return [5, 4];
  if (safeCount === 10) return [5, 5];
  if (safeCount <= 14) return [7, safeCount - 7];

  const rows = Math.ceil(safeCount / 7);
  const baseSize = Math.floor(safeCount / rows);
  const remainder = safeCount % rows;

  return Array.from({ length: rows }, (_, index) => baseSize + (index < remainder ? 1 : 0));
};

const getForecastRowWidth = (count) =>
  (count * FORECAST_DESKTOP_CARD_WIDTH) + (Math.max(0, count - 1) * FORECAST_DESKTOP_GAP);

const splitForecastDays = (days = []) => {
  const rows = [];
  let startIndex = 0;

  getForecastRowLayout(days.length).forEach((rowSize) => {
    rows.push(days.slice(startIndex, startIndex + rowSize));
    startIndex += rowSize;
  });

  return rows;
};

const resizeTextareaToContent = (element) => {
  if (!element) return;
  element.style.height = "auto";
  element.style.height = `${element.scrollHeight}px`;
};

const DEFAULT_PACKING_PROFILE = {
  gender: "unspecified",
  traveling_with_pet: false,
  has_allergies: false,
  traveling_with_children: false,
  always_include_items: [],
};
const DEFAULT_TRIP_OPTIONS = {
  trip_type: "city_break",
  trip_activities: [],
  baggage_format: "suitcase",
  accommodation_type: "hotel",
  laundry_access: "limited",
  packing_style: "balanced",
  adults: 2,
  children_ages: [],
  child_profiles: [],
  trip_note: "",
};
const INITIAL_TRIP_OPTIONS = {
  ...DEFAULT_TRIP_OPTIONS,
  baggage_format: "",
  accommodation_type: "",
  laundry_access: "",
  packing_style: "",
};
const LEGACY_TRIP_TYPE_MAP = {
  vacation: "city_break",
  city_break: "city_break",
  city: "city_break",
  business: "business_trip",
  business_trip: "business_trip",
  active: "outdoor_adventure",
  beach: "beach_escape",
  beach_escape: "beach_escape",
  winter: "winter_trip",
  winter_trip: "winter_trip",
  family: "family_trip",
  family_trip: "family_trip",
  romantic: "romantic_getaway",
  romantic_getaway: "romantic_getaway",
  camping: "outdoor_adventure",
  outdoor_adventure: "outdoor_adventure",
};

const normalizeTripType = (value) => LEGACY_TRIP_TYPE_MAP[(value || "").toString().trim().toLowerCase()] || DEFAULT_TRIP_OPTIONS.trip_type;
const normalizeTripActivities = (values = []) => {
  const normalized = [];
  (Array.isArray(values) ? values : []).forEach((rawValue) => {
    const value = (rawValue || "").toString().trim();
    if (!value || normalized.includes(value)) return;
    normalized.push(value);
  });
  return normalized;
};

const normalizeAdultsCount = (value, fallback = 2) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? Math.max(1, parsed) : fallback;
};

const normalizeChildrenAges = (values = []) => (
  (Array.isArray(values) ? values : [])
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => Number.isFinite(value) && value >= 0 && value <= 17)
    .slice(0, 8)
);

const resizeChildrenAges = (values = [], count = 0, fallbackAge = 7) => {
  const normalizedValues = normalizeChildrenAges(values);
  const nextCount = Math.max(0, Number.parseInt(count, 10) || 0);
  if (normalizedValues.length >= nextCount) {
    return normalizedValues.slice(0, nextCount);
  }
  return [...normalizedValues, ...Array.from({ length: nextCount - normalizedValues.length }, () => fallbackAge)];
};

const normalizeChildProfiles = (profiles = [], childrenAges = []) => {
  const rawProfiles = Array.isArray(profiles) ? profiles : [];
  return childrenAges.map((age, index) => {
    const rawProfile = rawProfiles[index] || {};
    const fallbackId = `child_${index + 1}`;
    const rawId = (rawProfile.id || "").toString().replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 48);
    return {
      id: rawId || fallbackId,
      name: (rawProfile.name || "").toString().trim().slice(0, 40),
      age,
      linked_user_id: normalizeUserId(rawProfile.linked_user_id) || null,
    };
  });
};

const normalizeTripParty = (value = {}) => {
  const adults = normalizeAdultsCount(value?.adults, DEFAULT_TRIP_OPTIONS.adults);
  const childrenAges = resizeChildrenAges(value?.children_ages, normalizeChildrenAges(value?.children_ages).length);
  return {
    adults,
    children_ages: childrenAges,
    child_profiles: normalizeChildProfiles(value?.child_profiles, childrenAges),
  };
};

const getTripPartyCounts = (value = {}) => {
  const normalized = normalizeTripParty(value);
  return {
    adults: normalized.adults,
    childrenCount: normalized.children_ages.length,
  };
};

const buildHotelChildrenAges = (value = {}) => {
  const normalized = normalizeTripParty(value);
  return normalized.children_ages;
};

const normalizeHotelRoomsCount = (value, travelersCount = 1) => {
  const parsed = Number.parseInt(value, 10);
  const maxRooms = Math.max(1, Math.min(Number.parseInt(travelersCount, 10) || 1, 8));
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), maxRooms);
};

const buildAccommodationUnitPlan = ({ adults = 1, childrenAges = [], units = 1 }) => {
  const normalizedAdults = Math.max(Number.parseInt(adults, 10) || 1, 1);
  const normalizedChildrenAges = normalizeChildrenAges(childrenAges);
  const totalGuests = Math.max(normalizedAdults + normalizedChildrenAges.length, 1);
  const unitCount = normalizeHotelRoomsCount(units, totalGuests);
  const groups = Array.from({ length: unitCount }, () => ({ adults: 0, children_ages: [] }));

  const pickTargetIndex = (preferAdultHost = false) => (
    groups.reduce((bestIndex, group, index) => {
      const bestGroup = groups[bestIndex];
      const groupGuests = group.adults + group.children_ages.length;
      const bestGuests = bestGroup.adults + bestGroup.children_ages.length;
      if (groupGuests !== bestGuests) {
        return groupGuests < bestGuests ? index : bestIndex;
      }
      if (preferAdultHost && group.adults !== bestGroup.adults) {
        return group.adults > bestGroup.adults ? index : bestIndex;
      }
      if (group.children_ages.length !== bestGroup.children_ages.length) {
        return group.children_ages.length < bestGroup.children_ages.length ? index : bestIndex;
      }
      return index < bestIndex ? index : bestIndex;
    }, 0)
  );

  for (let index = 0; index < normalizedAdults; index += 1) {
    groups[pickTargetIndex(false)].adults += 1;
  }

  normalizedChildrenAges.forEach((age) => {
    groups[pickTargetIndex(true)].children_ages.push(age);
  });

  groups.forEach((group) => {
    if (group.adults > 0 || group.children_ages.length === 0) return;
    const donorIndex = groups.findIndex((candidate) => candidate.adults > 1);
    if (donorIndex >= 0) {
      groups[donorIndex].adults -= 1;
      group.adults += 1;
    }
  });

  const normalizedGroups = groups.map((group) => ({
    adults: group.adults,
    children_ages: [...group.children_ages].sort((left, right) => left - right),
    total_guests: group.adults + group.children_ages.length,
  }));

  const representativeGroup = normalizedGroups.reduce((best, group) => {
    if (!best) return group;
    if (group.total_guests !== best.total_guests) {
      return group.total_guests > best.total_guests ? group : best;
    }
    if (group.adults !== best.adults) {
      return group.adults > best.adults ? group : best;
    }
    return group.children_ages.length > best.children_ages.length ? group : best;
  }, null) || { adults: normalizedAdults, children_ages: normalizedChildrenAges, total_guests: totalGuests };

  return {
    unit_count: unitCount,
    total_guests: totalGuests,
    groups: normalizedGroups,
    representative_group: representativeGroup,
  };
};

const formatRuProviderHint = (providerName, plan, lang = "ru") => {
  if (!plan) return "";
  if (plan.unit_count <= 1) {
    return providerName === "sutochno"
      ? (lang === "en" ? "Whole apartment or house for the group" : "Целое жильё для всей компании")
      : (lang === "en" ? "Hotels and apartments for the whole group" : "Отели и апартаменты для всей компании");
  }
  return providerName === "sutochno"
    ? (lang === "en" ? "Split across several apartments or homes" : "Делим поездку на несколько квартир или домов")
    : (lang === "en" ? "Split search across several stays" : "Делим поиск на несколько вариантов");
};

const normalizeHotelRating = (value) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return 0;
  return Math.min(parsed, 10);
};

const normalizeHotelPriceValue = (value) => {
  const digits = String(value ?? "").replace(/[^\d]/g, "");
  if (!digits) return "";
  const parsed = Number.parseInt(digits, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? String(parsed) : "";
};

const normalizeHotelBedroomsValue = (value) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) return 0;
  return Math.min(parsed, 6);
};

const getFlightPassengerCounts = (value = {}) => {
  const normalized = normalizeTripParty(value);
  const flightAdults = normalized.adults + normalized.children_ages.filter((age) => age >= 12).length;
  const flightChildren = normalized.children_ages.filter((age) => age >= 2 && age <= 11).length;
  const infants = normalized.children_ages.filter((age) => age < 2).length;
  return {
    adults: Math.max(1, flightAdults),
    children: flightChildren,
    infants,
  };
};

const formatTripPartySummary = (value = {}, lang = "ru") => {
  const { adults, childrenCount } = getTripPartyCounts(value);
  const segments = [
    `${adults} ${lang === "en" ? (adults === 1 ? "adult" : "adults") : adults === 1 ? "взрослый" : "взрослых"}`,
  ];
  if (childrenCount > 0) {
    segments.push(`${childrenCount} ${lang === "en" ? (childrenCount === 1 ? "child" : "children") : childrenCount === 1 ? "ребенок" : "детей"}`);
  }
  return segments.join(" · ");
};

const formatHotelCurrencyPrice = (currency = "RUB", value, lang = "ru") => {
  if (!Number.isFinite(Number(value))) return "";
  const amount = Math.round(Number(value)).toLocaleString(lang === "en" ? "en-US" : "ru-RU");
  if (currency === "RUB") return `${amount} ₽`;
  if (currency === "USD") return `$${amount}`;
  if (currency === "EUR") return `€${amount}`;
  return `${currency} ${amount}`;
};

const EXPENSE_BASE_CURRENCIES = ["RUB", "USD", "EUR"];
const EXPENSE_COMMON_CURRENCIES = [
  "RUB", "USD", "EUR", "GBP", "CHF",
  "TRY", "AED", "GEL", "AMD", "AZN", "KZT",
  "THB", "VND", "IDR", "CNY", "JPY", "KRW", "INR",
  "CZK", "HUF", "PLN", "NOK", "SEK", "DKK",
  "EGP", "MAD", "ILS", "MXN", "BRL", "CAD", "AUD",
];
const EXPENSE_CATEGORIES = [
  "food",
  "transport",
  "tickets",
  "hotel",
  "entertainment",
  "shopping",
  "other",
];

const COUNTRY_CURRENCY_BY_NAME = {
  russia: "RUB",
  россия: "RUB",
  "united states": "USD",
  usa: "USD",
  сша: "USD",
  "united arab emirates": "AED",
  uae: "AED",
  оаэ: "AED",
  moldova: "MDL",
  молдова: "MDL",
  turkey: "TRY",
  turkiye: "TRY",
  türkiye: "TRY",
  турция: "TRY",
  georgia: "GEL",
  грузия: "GEL",
  armenia: "AMD",
  армения: "AMD",
  azerbaijan: "AZN",
  азербайджан: "AZN",
  kazakhstan: "KZT",
  казахстан: "KZT",
  thailand: "THB",
  таиланд: "THB",
  vietnam: "VND",
  вьетнам: "VND",
  indonesia: "IDR",
  индонезия: "IDR",
  china: "CNY",
  китай: "CNY",
  japan: "JPY",
  япония: "JPY",
  "south korea": "KRW",
  korea: "KRW",
  "южная корея": "KRW",
  india: "INR",
  индия: "INR",
  "united kingdom": "GBP",
  uk: "GBP",
  "great britain": "GBP",
  великобритания: "GBP",
  switzerland: "CHF",
  швейцария: "CHF",
  czechia: "CZK",
  "czech republic": "CZK",
  чехия: "CZK",
  hungary: "HUF",
  венгрия: "HUF",
  poland: "PLN",
  польша: "PLN",
  norway: "NOK",
  норвегия: "NOK",
  sweden: "SEK",
  швеция: "SEK",
  denmark: "DKK",
  дания: "DKK",
  egypt: "EGP",
  египет: "EGP",
  morocco: "MAD",
  марокко: "MAD",
  israel: "ILS",
  израиль: "ILS",
  mexico: "MXN",
  мексика: "MXN",
  brazil: "BRL",
  бразилия: "BRL",
  canada: "CAD",
  канада: "CAD",
  australia: "AUD",
  австралия: "AUD",
  france: "EUR",
  франция: "EUR",
  italy: "EUR",
  италия: "EUR",
  spain: "EUR",
  испания: "EUR",
  germany: "EUR",
  германия: "EUR",
  austria: "EUR",
  австрия: "EUR",
  greece: "EUR",
  греция: "EUR",
  netherlands: "EUR",
  нидерланды: "EUR",
  portugal: "EUR",
  португалия: "EUR",
  finland: "EUR",
  финляндия: "EUR",
};

const CITY_CURRENCY_BY_NAME = {
  dubai: "AED",
  дубай: "AED",
  istanbul: "TRY",
  стамбул: "TRY",
  antalya: "TRY",
  анталия: "TRY",
  tbilisi: "GEL",
  тбилиси: "GEL",
  yerevan: "AMD",
  ереван: "AMD",
  baku: "AZN",
  баку: "AZN",
  chisinau: "MDL",
  chișinău: "MDL",
  кишинев: "MDL",
  кишинёв: "MDL",
  almaty: "KZT",
  алматы: "KZT",
  bangkok: "THB",
  бангкок: "THB",
  phuket: "THB",
  пхукет: "THB",
  budapest: "HUF",
  будапешт: "HUF",
  prague: "CZK",
  прага: "CZK",
  warsaw: "PLN",
  варшава: "PLN",
  london: "GBP",
  лондон: "GBP",
  tokyo: "JPY",
  токио: "JPY",
  seoul: "KRW",
  сеул: "KRW",
};

const normalizeExpenseCurrency = (value = "RUB") => {
  const normalized = String(value || "RUB").trim().toUpperCase();
  return /^[A-Z]{3}$/.test(normalized) ? normalized : "RUB";
};

const getPrimaryExpenseDestination = (checklist = {}) => {
  const rawCity = String(checklist?.destinations?.[0]?.city || checklist?.city || "").trim();
  return rawCity.split(" + ")[0]?.trim() || rawCity;
};

const getExpenseLocalCurrency = (checklist = {}) => {
  const destination = getPrimaryExpenseDestination(checklist);
  if (!destination) return normalizeExpenseCurrency(checklist?.expense_base_currency || "RUB");
  const parts = destination.split(",").map((part) => part.trim()).filter(Boolean);
  const country = parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
  const city = (parts[0] || destination).toLowerCase();
  return normalizeExpenseCurrency(
    COUNTRY_CURRENCY_BY_NAME[country]
    || CITY_CURRENCY_BY_NAME[city]
    || checklist?.expense_base_currency
    || "RUB"
  );
};

const buildExpenseCurrencyOptions = (...currencies) => {
  const normalizedCurrencies = currencies
    .flat()
    .filter(Boolean)
    .map((currency) => normalizeExpenseCurrency(currency));
  return Array.from(new Set(normalizedCurrencies)).map((currency) => ({
    id: currency,
    label: currency,
  }));
};

const normalizeExpenseAmountInput = (value) => {
  const normalized = String(value ?? "").replace(",", ".").replace(/[^\d.]/g, "");
  const firstDot = normalized.indexOf(".");
  if (firstDot === -1) return normalized;
  return normalized.slice(0, firstDot + 1) + normalized.slice(firstDot + 1).replace(/\./g, "");
};

const formatMoney = (value, currency = "RUB", lang = "ru") => {
  if (!Number.isFinite(Number(value))) return "";
  const amount = Number(value);
  const locale = lang === "en" ? "en-US" : "ru-RU";
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: normalizeExpenseCurrency(currency),
      maximumFractionDigits: amount % 1 === 0 ? 0 : 2,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString(locale)} ${currency}`;
  }
};

const getExpenseCategoryLabel = (category = "other", lang = "ru") => {
  const labels = {
    food: { ru: "Еда", en: "Food" },
    transport: { ru: "Транспорт", en: "Transport" },
    tickets: { ru: "Билеты", en: "Tickets" },
    hotel: { ru: "Жильё", en: "Accommodation" },
    entertainment: { ru: "Развлечения", en: "Entertainment" },
    shopping: { ru: "Покупки", en: "Shopping" },
    other: { ru: "Другое", en: "Other" },
  };
  return labels[category]?.[lang] || labels.other[lang] || labels.other.ru;
};

const getEventCoordinates = (event) => {
  if (event?.lat === null || event?.lat === undefined || event?.lat === "") return null;
  if (event?.lng === null || event?.lng === undefined || event?.lng === "") return null;
  const lat = Number(event?.lat);
  const lng = Number(event?.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return [lat, lng];
};

const getFlightClassOptions = (lang = "ru") => [
  { value: "0", label: lang === "en" ? "Economy" : "Эконом" },
  { value: "1", label: lang === "en" ? "Business" : "Бизнес" },
  { value: "2", label: lang === "en" ? "First" : "Первый" },
];

const normalizeSelectableOption = (value, allowedValues, fallback, preserveEmptySelections = false) => {
  const normalizedValue = (value ?? "").toString().trim();
  if (preserveEmptySelections && !normalizedValue) return "";
  return allowedValues.includes(normalizedValue) ? normalizedValue : fallback;
};

const normalizeTripOptions = (value = {}, { preserveEmptySelections = false } = {}) => ({
  trip_type: normalizeTripType(value?.trip_type),
  trip_activities: normalizeTripActivities(value?.trip_activities),
  baggage_format: normalizeSelectableOption(
    value?.baggage_format,
    ["carry_on", "suitcase", "suitcase_plus_carry_on", "hiking_backpack"],
    DEFAULT_TRIP_OPTIONS.baggage_format,
    preserveEmptySelections
  ),
  accommodation_type: normalizeSelectableOption(
    value?.accommodation_type,
    ["hotel", "apartment", "hostel", "camping"],
    DEFAULT_TRIP_OPTIONS.accommodation_type,
    preserveEmptySelections
  ),
  laundry_access: normalizeSelectableOption(
    value?.laundry_access,
    ["none", "limited", "easy"],
    DEFAULT_TRIP_OPTIONS.laundry_access,
    preserveEmptySelections
  ),
  packing_style: normalizeSelectableOption(
    value?.packing_style,
    ["light", "balanced", "prepared"],
    DEFAULT_TRIP_OPTIONS.packing_style,
    preserveEmptySelections
  ),
  ...normalizeTripParty(value),
  trip_note: (value?.trip_note || "").toString(),
});
const normalizePackingProfileItems = (items = []) => {
  const normalized = [];
  (Array.isArray(items) ? items : []).forEach((rawValue) => {
    const item = String(rawValue || "").trim();
    if (!item || normalized.includes(item)) return;
    normalized.push(item);
  });
  return normalized;
};

const normalizePackingProfile = (value = {}) => {
  const rawGender = String(value?.gender || "").trim().toLowerCase();
  const gender = ["male", "female"].includes(rawGender) ? rawGender : "unspecified";
  return {
    gender,
    traveling_with_pet: Boolean(value?.traveling_with_pet),
    has_allergies: Boolean(value?.has_allergies),
    traveling_with_children: Boolean(value?.traveling_with_children),
    always_include_items: normalizePackingProfileItems(value?.always_include_items),
  };
};

const buildCheckedItemsMap = (items = [], checkedItems = [], quantityMap = {}, packedMap = {}) => {
  const checkedSet = new Set(checkedItems || []);
  const normalizedQuantities = getNormalizedQuantityMap(quantityMap);
  const normalizedPacked = getNormalizedPackedQuantityMap(packedMap);
  return items.reduce((acc, item) => {
    const normalizedKey = normalizeItemKey(item);
    const needed = normalizedKey ? (normalizedQuantities[normalizedKey] || 1) : 1;
    const packed = normalizedKey ? (normalizedPacked[normalizedKey] || 0) : 0;
    acc[item] = packed >= needed || checkedSet.has(item);
    return acc;
  }, {});
};

const CHECKLIST_CATEGORY_OPTIONS = {
  ru: ["Важное", "Документы", "Одежда", "Гигиена", "Техника", "Аптечка", "Для детей", "Кемпинг", "Прочее"],
  en: ["Essentials", "Documents", "Clothes", "Hygiene", "Electronics", "Pharmacy", "Kids", "Camping", "Misc"],
};

const formatBaggageCount = (count, lang = "ru") =>
  pluralize(count, ["багаж", "багажа", "багажа"], ["bag", "bags"], lang);

const formatItemCount = (count, lang = "ru") =>
  pluralize(count, ["вещь", "вещи", "вещей"], ["item", "items"], lang);

const formatBaggageSummary = (baggageCount, itemCount, lang = "ru") =>
  `${formatBaggageCount(baggageCount, lang)} • ${formatItemCount(itemCount, lang)}`;

const formatChecklistLocale = (lang = "ru") => (lang === "en" ? "en-US" : "ru-RU");

const renderChecklistHeaderDate = (dateStr, lang = "ru") => {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const formatter = new Intl.DateTimeFormat(formatChecklistLocale(lang), { day: "numeric", month: "long" });
  const parts = formatter.formatToParts(date);
  const day = parts.find((part) => part.type === "day")?.value || "";
  const month = parts.find((part) => part.type === "month")?.value || formatter.format(date);

  if (lang === "en") {
    return <>{month} <span className="date-num">{day}</span></>;
  }

  return <><span className="date-num">{day}</span> {month}</>;
};

const CHECKLIST_CATEGORY_KEYWORDS = {
  ru: {
    "Важное": ["паспорт", "страхов", "деньги", "карта", "виза", "билет", "бронь", "удостоверение", "документ"],
    "Документы": ["рецепт", "заключение", "аллерген", "разговорник"],
    "Одежда": ["курт", "футбол", "джинс", "шорт", "свит", "брюк", "кроссов", "обув", "пижам", "купаль", "плавк", "шап", "шарф", "перчат", "носк", "бель", "рубаш", "худи", "ботин", "плать", "юбк", "полотен"],
    "Гигиена": ["щетк", "паста", "дезодорант", "мыло", "шампун", "расчес", "космет", "салфет", "крем", "антисеп", "бритв", "ватн"],
    "Техника": ["телефон", "заряд", "power bank", "пауэр", "науш", "ноутбук", "кабель", "адаптер", "переходник", "камера", "фотоаппарат"],
    "Аптечка": ["лекар", "обезбол", "пластыр", "антигист", "уголь", "сорб", "аптеч", "репелл", "диаре", "укач", "горла"],
    "Для детей": ["дет", "ребен", "ребён", "пампер", "подгуз", "коляск", "поиль", "бутылоч", "игруш"],
    "Кемпинг": ["палат", "спальн", "карим", "коврик", "горелк", "мультитул", "паракорд", "гермом", "фонар"],
  },
  en: {
    "Essentials": ["passport", "insurance", "cash", "card", "visa", "ticket", "booking", "license", "document"],
    "Documents": ["prescription", "medical report", "allerg", "phrasebook"],
    "Clothes": ["jacket", "t-shirt", "jeans", "shorts", "sweater", "pants", "shoes", "sneakers", "pajamas", "swimsuit", "hat", "scarf", "gloves", "socks", "underwear", "shirt", "hoodie", "boots", "dress", "towel"],
    "Hygiene": ["tooth", "deodor", "soap", "shampoo", "hairbrush", "makeup", "wipes", "cream", "sanitizer", "shaving", "cotton"],
    "Electronics": ["phone", "charger", "power bank", "headphones", "laptop", "cable", "adapter", "camera"],
    "Pharmacy": ["med", "pain", "plaster", "antihist", "charcoal", "first aid", "repellent", "diarrhea", "motion sickness", "throat"],
    "Kids": ["baby", "kids", "diaper", "stroller", "sippy", "toy"],
    "Camping": ["tent", "sleep", "camp", "multitool", "rope", "dry bag", "flashlight"],
  },
};

const normalizeItemCategoryMap = (value = {}) =>
  Object.entries(value || {}).reduce((acc, [key, rawValue]) => {
    const normalizedKey = normalizeItemKey(key);
    const category = String(rawValue || "").trim();
    if (!normalizedKey || !category) return acc;
    acc[normalizedKey] = category;
    return acc;
  }, {});

const normalizeItemTranslationMap = (value = {}) => normalizeChecklistItemTranslations(value);

const mergeItemTranslationEntry = (translationMap = {}, item, entry) => {
  const itemLabel = String(item || "").trim();
  if (!itemLabel || !entry || typeof entry !== "object") {
    return normalizeItemTranslationMap(translationMap);
  }
  const nextMap = normalizeItemTranslationMap(translationMap);
  nextMap[itemLabel] = {
    ...(nextMap[itemLabel] || {}),
    ...entry,
  };
  return nextMap;
};

const getItemCategory = (categoryMap = {}, item) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return "";
  return normalizeItemCategoryMap(categoryMap)[normalizedKey] || "";
};

const setItemCategoryInMap = (categoryMap = {}, item, nextCategory) => {
  const normalizedKey = normalizeItemKey(item);
  if (!normalizedKey) return normalizeItemCategoryMap(categoryMap);
  const nextMap = normalizeItemCategoryMap(categoryMap);
  const category = String(nextCategory || "").trim();
  if (!category) {
    delete nextMap[normalizedKey];
    return nextMap;
  }
  nextMap[normalizedKey] = category;
  return nextMap;
};

const inferItemCategory = (item, lang = "ru", categoryMap = {}) => {
  const explicit = getItemCategory(categoryMap, item);
  if (explicit) return translateChecklistCategoryLabel(explicit, lang);
  const normalized = normalizeItemKey(item);
  const keywords = CHECKLIST_CATEGORY_KEYWORDS[lang] || CHECKLIST_CATEGORY_KEYWORDS.ru;
  const matched = Object.entries(keywords).find(([, values]) => values.some((value) => normalized.includes(normalizeItemKey(value))));
  if (matched) return matched[0];
  const fallback = CHECKLIST_CATEGORY_OPTIONS[lang] || CHECKLIST_CATEGORY_OPTIONS.ru;
  return fallback[fallback.length - 1];
};

const buildChecklistCategorySections = (items = [], categoryMap = {}, lang = "ru") => {
  const grouped = new Map();
  items.forEach((item) => {
    const category = inferItemCategory(item, lang, categoryMap);
    if (!grouped.has(category)) grouped.set(category, []);
    grouped.get(category).push(item);
  });

  const preferredOrder = CHECKLIST_CATEGORY_OPTIONS[lang] || CHECKLIST_CATEGORY_OPTIONS.ru;
  const orderedCategories = [
    ...preferredOrder.filter((category) => grouped.has(category)),
    ...Array.from(grouped.keys()).filter((category) => !preferredOrder.includes(category)).sort((a, b) => a.localeCompare(b, lang)),
  ];

  return orderedCategories.map((category) => ({
    category,
    items: grouped.get(category) || [],
  }));
};

const buildChecklistColumns = (sections = [], columnCount = 3) => {
  const requestedColumnCount = Math.max(1, Number(columnCount) || 1);
  const totalItems = sections.reduce((sum, section) => sum + (section.items?.length || 0), 0);
  const safeColumnCount = Math.min(requestedColumnCount, Math.max(1, totalItems || 1));

  if (safeColumnCount === 1) return [sections];
  if (totalItems === 0) return Array.from({ length: safeColumnCount }, () => []);

  const baseTarget = Math.floor(totalItems / safeColumnCount);
  const remainder = totalItems % safeColumnCount;
  const columnTargets = Array.from({ length: safeColumnCount }, (_, index) => baseTarget + (index < remainder ? 1 : 0));
  const columns = Array.from({ length: safeColumnCount }, () => []);

  let columnIndex = 0;
  let filledInColumn = 0;

  sections.forEach((section) => {
    const items = Array.isArray(section.items) ? section.items : [];
    let offset = 0;

    while (offset < items.length && columnIndex < safeColumnCount) {
      const isLastColumn = columnIndex === safeColumnCount - 1;
      const remainingInColumn = Math.max(columnTargets[columnIndex] - filledInColumn, 0);
      const remainingItems = items.length - offset;
      let takeCount = isLastColumn
        ? remainingItems
        : Math.min(remainingItems, Math.max(1, remainingInColumn));
      const wouldMoveToNextColumn = !isLastColumn && takeCount < remainingItems;
      const movedItemCount = remainingItems - takeCount;
      if (wouldMoveToNextColumn && movedItemCount < 3) {
        takeCount = remainingItems;
      }

      columns[columnIndex].push({
        ...section,
        key: `${section.category}-${offset}-${columnIndex}`,
        isContinuation: offset > 0,
        items: items.slice(offset, offset + takeCount),
      });

      offset += takeCount;
      filledInColumn += takeCount;

      if (!isLastColumn && filledInColumn >= columnTargets[columnIndex]) {
        columnIndex += 1;
        filledInColumn = 0;
      }
    }
  });

  return columns;
};

const getBaggageEditorIds = (baggage) =>
  Array.isArray(baggage?.editor_user_ids)
    ? baggage.editor_user_ids.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0)
    : [];

const getOwnerBaggageEditorIds = (backpacks = [], ownerUserId, fallbackBaggage = null) => {
  const uniqueIds = [];
  const scopedChildProfileId = fallbackBaggage?.child_profile_id || null;
  (backpacks || []).forEach((baggage) => {
    if (baggage.user_id !== ownerUserId) return;
    if ((baggage.child_profile_id || null) !== scopedChildProfileId) return;
    getBaggageEditorIds(baggage).forEach((editorId) => {
      if (!uniqueIds.includes(editorId)) {
        uniqueIds.push(editorId);
      }
    });
  });
  if (uniqueIds.length > 0) {
    return uniqueIds;
  }
  return fallbackBaggage ? getBaggageEditorIds(fallbackBaggage) : [];
};

const canUserEditBaggage = (baggage, userId, allBackpacks = [], checklist = null) => {
  if (!baggage || !userId) return false;
  if (baggage.user_id === userId) return true;
  if (baggage.child_profile_id && checklist?.user_id === userId) return true;
  return getOwnerBaggageEditorIds(allBackpacks, baggage.user_id, baggage).includes(userId);
};

const getChildProfileDisplayName = (profile, lang = "ru", index = 0) => {
  const name = (profile?.name || "").trim();
  if (name) return name;
  return lang === "en" ? `Child ${index + 1}` : `Ребенок ${index + 1}`;
};

const sortBaggageList = (items = []) =>
  [...items].sort((a, b) => {
    if (Boolean(b.is_default) !== Boolean(a.is_default)) {
      return Number(Boolean(b.is_default)) - Number(Boolean(a.is_default));
    }
    if ((a.sort_order || 0) !== (b.sort_order || 0)) {
      return (a.sort_order || 0) - (b.sort_order || 0);
    }
    return (a.id || 0) - (b.id || 0);
  });

const sortAllBackpacks = (items = []) =>
  [...items].sort((a, b) => {
    if ((a.user_id || 0) !== (b.user_id || 0)) return (a.user_id || 0) - (b.user_id || 0);
    if (Boolean(b.is_default) !== Boolean(a.is_default)) {
      return Number(Boolean(b.is_default)) - Number(Boolean(a.is_default));
    }
    if ((a.sort_order || 0) !== (b.sort_order || 0)) {
      return (a.sort_order || 0) - (b.sort_order || 0);
    }
    return (a.id || 0) - (b.id || 0);
  });

const getItineraryEventSortTime = (event) => {
  const explicitTime = String(event?.time || "").trim();
  if (explicitTime) return explicitTime;
  const meta = event?.meta && typeof event.meta === "object" ? event.meta : {};
  const dayPart = String(meta.day_part || event?.day_part || "").toLowerCase();
  if (dayPart.includes("morning") || dayPart.includes("breakfast") || dayPart.includes("утро") || dayPart.includes("завтрак")) return "09:00";
  if (dayPart.includes("evening") || dayPart.includes("dinner") || dayPart.includes("вечер") || dayPart.includes("ужин")) return "19:00";
  if (dayPart.includes("day") || dayPart.includes("afternoon") || dayPart.includes("lunch") || dayPart.includes("день") || dayPart.includes("обед")) return "13:00";
  const eventType = String(event?.event_type || "").toLowerCase();
  if (["food", "restaurant", "cafe"].includes(eventType)) return "13:00";
  return "99:99";
};

const compareItineraryEvents = (a, b) => (
  String(a?.event_date || "").localeCompare(String(b?.event_date || ""))
  || getItineraryEventSortTime(a).localeCompare(getItineraryEventSortTime(b))
  || String(a?.title || "").localeCompare(String(b?.title || ""))
);

const parseItineraryTimeToMinutes = (value) => {
  const match = /^(\d{2}):(\d{2})$/.exec(String(value || "").trim());
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes) || hours > 23 || minutes > 59) return null;
  return hours * 60 + minutes;
};

const formatItineraryMinutes = (value) => {
  const minutes = Math.max(6 * 60, Math.min(value, 23 * 60 + 30));
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
};

const getItineraryEventDuration = (event) => {
  const explicitDuration = Number(event?.duration_minutes);
  if (Number.isFinite(explicitDuration) && explicitDuration > 0) return explicitDuration;
  const eventType = String(event?.event_type || "").toLowerCase();
  if (["food", "restaurant"].includes(eventType)) return 75;
  if (eventType === "cafe") return 60;
  if (eventType === "walk") return 50;
  if (eventType === "shopping") return 75;
  if (["museum", "sight", "attraction"].includes(eventType)) return eventType === "museum" ? 105 : 90;
  return 75;
};

const getItineraryEventGap = (event) => {
  const explicitGap = Number(event?.travel_buffer_minutes);
  if (Number.isFinite(explicitGap) && explicitGap >= 0) return Math.min(explicitGap, 90);
  return 15;
};

const buildCascadedEventTimeUpdates = (events, updatedEvent) => {
  const updatedMinutes = parseItineraryTimeToMinutes(updatedEvent?.time);
  if (updatedMinutes === null || !updatedEvent?.event_date) return [];
  const sameDayEvents = (events || [])
    .filter((event) => event.id !== updatedEvent.id && event.event_date === updatedEvent.event_date)
    .filter((event) => parseItineraryTimeToMinutes(event.time) !== null)
    .sort(compareItineraryEvents);

  let cursor = updatedMinutes + getItineraryEventDuration(updatedEvent) + getItineraryEventGap(updatedEvent);
  const updates = [];
  sameDayEvents
    .filter((event) => parseItineraryTimeToMinutes(event.time) >= updatedMinutes)
    .forEach((event) => {
      const eventMinutes = parseItineraryTimeToMinutes(event.time);
      if (eventMinutes < cursor) {
        const nextTime = formatItineraryMinutes(cursor);
        updates.push({ ...event, time: nextTime });
        cursor += getItineraryEventDuration(event) + getItineraryEventGap(event);
      } else {
        cursor = eventMinutes + getItineraryEventDuration(event) + getItineraryEventGap(event);
      }
    });
  return updates;
};

const buildBaggageParticipants = (checklist, currentUser, lang = "ru") => {
  const groups = new Map();
  const childProfiles = normalizeTripParty(checklist?.trip_profile || {}).child_profiles;
  const childProfileMap = new Map(childProfiles.map((profile, index) => [
    profile.id,
    {
      ...profile,
      index,
      linked_user_id: normalizeUserId(profile.linked_user_id) || null,
    },
  ]));

  const ensureGroup = (userId, username, extra = {}) => {
    if (!userId) return null;
    if (!groups.has(userId)) {
      groups.set(userId, {
        userId,
        username: username || `id:${userId}`,
        isCurrentUser: currentUser?.id === userId,
        isOwner: checklist?.user_id === userId,
        isChild: false,
        childProfileId: null,
        ownerUserId: null,
        age: null,
        linkedUserId: null,
        baggage: [],
        ...extra,
      });
    }
    const group = groups.get(userId);
    if (username) {
      group.username = username;
    }
    if (!group.isChild) {
      group.isCurrentUser = currentUser?.id === userId;
      group.isOwner = checklist?.user_id === userId;
    }
    return group;
  };

  (checklist?.backpacks || []).forEach((bp) => {
    const childProfileId = (bp.child_profile_id || "").trim();
    const childProfile = childProfileId ? childProfileMap.get(childProfileId) : null;
    const linkedUserId = normalizeUserId(childProfile?.linked_user_id);
    const group = childProfileId
      ? ensureGroup(
        linkedUserId || `child:${childProfileId}`,
        getChildProfileDisplayName(childProfile, lang, childProfile?.index || 0),
        {
          isChild: true,
          childProfileId,
          ownerUserId: checklist?.user_id || bp.user_id,
          age: childProfile?.age ?? null,
          linkedUserId: linkedUserId || null,
          isCurrentUser: Boolean(linkedUserId && currentUser?.id === linkedUserId),
          isOwner: false,
        },
      )
      : ensureGroup(bp.user_id, bp.user?.username || (currentUser?.id === bp.user_id ? currentUser.username : ""));
    if (group) {
      group.baggage.push(bp);
    }
  });

  if (currentUser && checklist?.user_id === currentUser.id) {
    childProfiles.forEach((profile, index) => {
      if (normalizeUserId(profile.linked_user_id)) return;
      ensureGroup(`child:${profile.id}`, getChildProfileDisplayName(profile, lang, index), {
        isChild: true,
        childProfileId: profile.id,
        ownerUserId: currentUser.id,
        age: profile.age ?? null,
        linkedUserId: null,
        isCurrentUser: false,
        isOwner: false,
      });
    });
  }

  if (currentUser && checklist?.user_id === currentUser.id) {
    ensureGroup(currentUser.id, currentUser.username);
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      baggage: sortBaggageList(group.baggage),
    }))
    .sort((a, b) => {
      if (a.isCurrentUser !== b.isCurrentUser) return a.isCurrentUser ? -1 : 1;
      if (a.isOwner !== b.isOwner) return a.isOwner ? -1 : 1;
      if (a.isChild !== b.isChild) return a.isChild ? 1 : -1;
      return a.username.localeCompare(b.username, formatChecklistLocale(lang));
    });
};

const getChecklistParticipantIds = (checklist) => {
  const ids = new Set();
  if (checklist?.user_id) {
    ids.add(normalizeUserId(checklist.user_id));
  }
  (checklist?.backpacks || []).forEach((backpack) => {
    if (backpack.user_id) {
      ids.add(normalizeUserId(backpack.user_id));
    }
  });
  return ids;
};

const guessBaggageKind = (name) => {
  const normalized = (name || "").trim().toLowerCase();
  if (!normalized) return "custom";
  if (normalized.includes("чемод") || normalized.includes("suitcase")) return "suitcase";
  if ((normalized.includes("ручн") && normalized.includes("клад")) || normalized.includes("carry-on") || normalized.includes("carry on")) return "carry_on";
  if (normalized.includes("рюкзак") || normalized.includes("backpack")) return "backpack";
  if (normalized.includes("сумк") || normalized.includes("bag")) return "bag";
  return "custom";
};

const getBaggageKindLabel = (baggage, lang = "ru") => {
  const kind = baggage?.kind || guessBaggageKind(baggage?.name || "");
  if (kind === "suitcase") return lang === "en" ? "Suitcase" : "Чемодан";
  if (kind === "carry_on") return lang === "en" ? "Carry-on" : "Ручная кладь";
  if (kind === "bag") return lang === "en" ? "Bag" : "Сумка";
  if (kind === "custom") return lang === "en" ? "Baggage" : "Багаж";
  return lang === "en" ? "Backpack" : "Рюкзак";
};

const getBaggageVisibleItemCount = (baggage) => {
  const items = baggage?.items || [];
  const removed = new Set(baggage?.removed_items || []);
  return items.filter((item) => !removed.has(item)).length;
};

const getParticipantVisibleItemCount = (participant) =>
  (participant?.baggage || []).reduce((sum, baggage) => sum + getBaggageVisibleItemCount(baggage), 0);

const getInitial = (value = "") => (value.trim().charAt(0) || "?").toUpperCase();

const getBaggageMetaLine = (baggage, lang = "ru") => {
  const name = (baggage?.name || "").trim().toLowerCase();
  const kindLabel = getBaggageKindLabel(baggage, lang);
  const count = getBaggageVisibleItemCount(baggage);
  const parts = [];

  if (kindLabel.trim().toLowerCase() !== name) {
    parts.push(kindLabel);
  }
  parts.push(formatItemCount(count, lang));
  return parts.join(" • ");
};

const clearBaggageStatePayload = () => ({
  items: [],
  checked_items: [],
  added_items: [],
  removed_items: [],
  item_quantities: {},
  packed_quantities: {},
  item_categories: {},
  item_translations: {},
});

const NOTIFICATION_CACHE_TTL_MS = 2000;
const notificationRequestCache = new Map();
const CHECKLIST_CACHE_TTL_MS = 12000;
const checklistRequestCache = new Map();

const getChecklistCacheKey = (checklistId, authHeaders = {}) =>
  `${authHeaders.Authorization || "__guest__"}:${checklistId}`;

const getCachedChecklistSnapshot = (checklistId, authHeaders = {}) => {
  const cached = checklistRequestCache.get(getChecklistCacheKey(checklistId, authHeaders));
  if (!cached?.data) return null;
  if (Date.now() - cached.timestamp > CHECKLIST_CACHE_TTL_MS) return null;
  return cached.data;
};

const writeChecklistCache = (checklistId, authHeaders = {}, data) => {
  if (!checklistId || !data) return;
  checklistRequestCache.set(getChecklistCacheKey(checklistId, authHeaders), {
    data,
    timestamp: Date.now(),
    promise: null,
  });
};

const readApiErrorMessage = async (response, fallbackMessage) => {
  try {
    const payload = await response.json();
    return payload?.detail || payload?.message || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
};

const fetchChecklistCached = async ({ checklistId, authHeaders = {} }) => {
  const cacheKey = getChecklistCacheKey(checklistId, authHeaders);
  const now = Date.now();
  const cached = checklistRequestCache.get(cacheKey);

  if (cached?.promise) {
    return cached.promise;
  }

  if (cached?.data && now - cached.timestamp < CHECKLIST_CACHE_TTL_MS) {
    return cached.data;
  }

  const promise = (async () => {
    const requestOptions = authHeaders.Authorization ? { headers: authHeaders } : undefined;
    let response = await fetch(`${API_URL}/checklist/${checklistId}`, requestOptions);
    if (response.status === 401 && authHeaders.Authorization) {
      response = await fetch(`${API_URL}/checklist/${checklistId}`);
    }
    if (!response.ok) {
      const fallbackMessage = response.status >= 500 ? "Сервер временно недоступен" : "Чеклист не найден";
      throw new Error(await readApiErrorMessage(response, fallbackMessage));
    }
    const data = await response.json();
    writeChecklistCache(checklistId, authHeaders, data);
    return data;
  })().catch((error) => {
    checklistRequestCache.delete(cacheKey);
    throw error;
  });

  checklistRequestCache.set(cacheKey, {
    data: cached?.data || null,
    timestamp: cached?.timestamp || 0,
    promise,
  });

  return promise;
};

const buildChecklistStatePayload = (checklist) => ({
  checked_items: checklist?.checked_items || [],
  removed_items: checklist?.removed_items || [],
  added_items: checklist?.added_items || [],
  items: checklist?.items || [],
  item_quantities: checklist?.item_quantities || {},
  packed_quantities: checklist?.packed_quantities || {},
  item_categories: checklist?.item_categories || {},
  item_translations: checklist?.item_translations || {},
  trip_profile: checklist?.trip_profile || undefined,
});

const buildBackpackStatePayload = (backpack) => ({
  checked_items: backpack?.checked_items || [],
  removed_items: backpack?.removed_items || [],
  added_items: backpack?.added_items || [],
  items: backpack?.items || [],
  item_quantities: backpack?.item_quantities || {},
  packed_quantities: backpack?.packed_quantities || {},
  item_categories: backpack?.item_categories || {},
  item_translations: backpack?.item_translations || {},
});

const fetchNotificationsCached = async (authHeaders = {}) => {
  const cacheKey = authHeaders.Authorization || "__guest__";
  const now = Date.now();
  const cached = notificationRequestCache.get(cacheKey);

  if (cached?.promise) {
    return cached.promise;
  }

  if (cached && now - cached.timestamp < NOTIFICATION_CACHE_TTL_MS) {
    return cached.data;
  }

  const promise = fetch(`${API_URL}/notifications`, { headers: authHeaders })
    .then((response) => (response.ok ? response.json() : []))
    .then((data) => {
      notificationRequestCache.set(cacheKey, {
        data,
        timestamp: Date.now(),
        promise: null,
      });
      return data;
    })
    .catch((error) => {
      notificationRequestCache.delete(cacheKey);
      throw error;
    });

  notificationRequestCache.set(cacheKey, {
    data: cached?.data || [],
    timestamp: cached?.timestamp || 0,
    promise,
  });

  return promise;
};

const NotificationBell = ({ authHeaders, lang, navigate }) => {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);
  const unreadCount = notifications.filter(n => !n.is_read).length;
  const refreshNotifications = React.useCallback(() => {
    fetchNotificationsCached(authHeaders)
      .then(setNotifications)
      .catch(e => console.error("Error fetching notifications:", e));
  }, [authHeaders]);

  useEffect(() => {
    refreshNotifications();
    const timer = setInterval(refreshNotifications, 30000);
    return () => clearInterval(timer);
  }, [refreshNotifications]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handlePointerDown = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [isOpen]);

  const markRead = async (id, link) => {
    try {
      await fetch(`${API_URL}/notifications/${id}/read`, {
        method: "PATCH",
        headers: authHeaders
      });
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      if (link && typeof link === 'string') {
        navigate(link);
        setIsOpen(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleInviteAction = async (e, notif, action) => {
    e.stopPropagation();
    const token = notif.extra_data?.token;
    if (!token && action === 'accept') return;

    try {
      if (action === 'accept') {
        const childProfileId = notif.extra_data?.child_profile_id;
        const joinUrl = new URL(`${API_URL}/join/${token}`, window.location.origin);
        if (childProfileId) {
          joinUrl.searchParams.set("child_profile_id", childProfileId);
        }
        const res = await fetch(joinUrl.toString(), {
          method: "POST",
          headers: authHeaders
        });
        if (res.ok) {
          const checklist = await res.json();
          if (window.location.pathname.includes(`/checklist/${checklist.slug}`)) {
            window.location.reload();
          } else {
            navigate(`/checklist/${checklist.slug}`);
          }
          setIsOpen(false);
        }
      }

      // Always mark as read
      await fetch(`${API_URL}/notifications/${notif.id}/read`, {
        method: "PATCH",
        headers: authHeaders
      });
      setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, is_read: true } : n));

      if (action === 'decline') {
        // Just refresh if we declined to update unread count locally
        refreshNotifications();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleFollowRequestAction = async (e, notif, action) => {
    e.stopPropagation();
    const requestId = notif.extra_data?.request_id;
    if (!requestId) return;

    try {
      const res = await fetch(`${API_URL}/follow-requests/${requestId}/${action}`, {
        method: "POST",
        headers: authHeaders
      });
      if (res.ok) {
        // Mark notification as read
        await fetch(`${API_URL}/notifications/${notif.id}/read`, {
          method: "PATCH",
          headers: authHeaders
        });
        setNotifications(prev => prev.map(n =>
          n.id === notif.id
            ? { ...n, is_read: true, _handled: action }
            : n
        ));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const markAllRead = async () => {
    const unreadIds = notifications.filter(n => !n.is_read).map(n => n.id);
    for (const id of unreadIds) {
      fetch(`${API_URL}/notifications/${id}/read`, { method: "PATCH", headers: authHeaders }).catch(e => console.error(e));
    }
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  return (
    <div className="notification-bell-container" ref={dropdownRef}>
      <button className="bell-btn" onClick={() => setIsOpen(!isOpen)}>
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="bell-svg"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && <span className="bell-badge">{unreadCount}</span>}
      </button>

      {isOpen && (
        <div className="notifications-dropdown">
          <div className="notif-header">
            <span>{lang === 'ru' ? 'Уведомления' : 'Notifications'}</span>
            {notifications.length > 0 && (
              <button
                className={`mark-all-btn ${unreadCount > 0 ? 'has-unread' : 'all-read'}`}
                onClick={markAllRead}
                title={lang === 'ru' ? 'Прочитать всё' : 'Mark all read'}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12l5 5L17 6" />
                  <path d="M7 12l5 5L23 6" />
                </svg>
              </button>
            )}
          </div>
          <div className="notif-list">
            {notifications.length > 0 ? notifications.map(n => (
              <div
                key={n.id}
                className={`notif-item ${!n.is_read ? 'unread' : ''}`}
                onClick={() => (n.type !== 'checklist_invitation' && n.type !== 'follow_request') && markRead(n.id, n.link)}
              >
                <div className="notif-content">{n.content}</div>
                {n.type === 'checklist_invitation' && !n.is_read && (
                  <div className="notif-actions">
                    <button
                      className="notif-action-btn accept"
                      onClick={(e) => handleInviteAction(e, n, 'accept')}
                    >
                      {lang === 'ru' ? 'Принять' : 'Accept'}
                    </button>
                    <button
                      className="notif-action-btn decline"
                      onClick={(e) => handleInviteAction(e, n, 'decline')}
                    >
                      {lang === 'ru' ? 'Отклонить' : 'Decline'}
                    </button>
                  </div>
                )}
                {n.type === 'follow_request' && !n.is_read && !n._handled && (
                  <div className="notif-actions">
                    <button
                      className="notif-action-btn accept"
                      onClick={(e) => handleFollowRequestAction(e, n, 'accept')}
                    >
                      {lang === 'ru' ? 'Принять' : 'Accept'}
                    </button>
                    <button
                      className="notif-action-btn decline"
                      onClick={(e) => handleFollowRequestAction(e, n, 'decline')}
                    >
                      {lang === 'ru' ? 'Отклонить' : 'Decline'}
                    </button>
                  </div>
                )}
                {n.type === 'follow_request' && n._handled && (
                  <div className="notif-actions">
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      {n._handled === 'accept'
                        ? (lang === 'ru' ? '✓ Принято' : '✓ Accepted')
                        : (lang === 'ru' ? '✗ Отклонено' : '✗ Declined')}
                    </span>
                  </div>
                )}
                <div className="notif-time">
                  {new Date(n.created_at).toLocaleDateString(lang === 'ru' ? 'ru-RU' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            )) : (
              <div className="notif-empty">
                {lang === 'ru' ? 'Нет уведомлений' : 'No notifications'}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const ChecklistRouteSkeleton = () => (
  <div className="results-section checklist-skeleton-shell" aria-hidden="true">
    <div className="checklist-skeleton-header">
      <div className="skeleton-block skeleton-text-xl checklist-skeleton-title" />
      <div className="skeleton-block skeleton-pill checklist-skeleton-action" />
    </div>

    <div className="checklist-skeleton-subtitle">
      <div className="skeleton-block skeleton-text-md" />
    </div>

    <div className="checklist-skeleton-summary">
      {Array.from({ length: 3 }, (_, index) => (
        <div key={index} className="skeleton-block skeleton-pill checklist-skeleton-chip" />
      ))}
    </div>

    <div className="checklist-skeleton-body">
      <div className="checklist-skeleton-sidebar">
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="checklist-skeleton-participant">
            <div className="skeleton-block checklist-skeleton-avatar" />
            <div className="checklist-skeleton-copy">
              <div className="skeleton-block skeleton-text-sm" />
              <div className="skeleton-block skeleton-text-xs" />
            </div>
          </div>
        ))}
      </div>

      <div className="checklist-skeleton-items">
        {Array.from({ length: 7 }, (_, index) => (
          <div key={index} className="checklist-skeleton-item">
            <div className="skeleton-block checklist-skeleton-checkbox" />
            <div className="checklist-skeleton-copy">
              <div className="skeleton-block skeleton-text-sm" />
              <div className="skeleton-block skeleton-text-xs" />
            </div>
            <div className="skeleton-block skeleton-pill checklist-skeleton-chip compact" />
          </div>
        ))}
      </div>
    </div>
  </div>
);

const TelegramLinkButton = ({
  user,
  token,
  onUserUpdate,
  lang,
  buttonClassName = "",
  hideLabel = false,
  onButtonClick = null,
  menuMode = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [linkInfo, setLinkInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [hint, setHint] = useState("");

  const loadLinkInfo = async () => {
    setLoading(true);
    setError("");
    setCopied(false);
    setHint("");
    try {
      const res = await fetch(`${API_URL}/auth/telegram/link`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to prepare Telegram link" : "Не удалось подготовить ссылку Telegram"));
      }
      setLinkInfo(data);
      return data;
    } catch (e) {
      console.error(e);
      const message = e.message || (lang === "en" ? "Failed to prepare Telegram link" : "Не удалось подготовить ссылку Telegram");
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const openModal = async () => {
    onButtonClick?.();
    setIsOpen(true);
    await loadLinkInfo();
  };

  const unlinkTelegram = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/telegram/link`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to unlink Telegram" : "Не удалось отвязать Telegram"));
      }
      onUserUpdate(data);
      return true;
    } catch (e) {
      console.error(e);
      setError(e.message || (lang === "en" ? "Failed to unlink Telegram" : "Не удалось отвязать Telegram"));
      return false;
    } finally {
      setLoading(false);
    }
  };

  const refreshStatus = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to refresh status" : "Не удалось обновить статус"));
      }
      onUserUpdate(data);
    } catch (e) {
      console.error(e);
      setError(e.message || (lang === "en" ? "Failed to refresh status" : "Не удалось обновить статус"));
    } finally {
      setLoading(false);
    }
  }, [lang, onUserUpdate, token]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleFocus = () => {
      if (!user?.tg_id) {
        refreshStatus();
      }
    };

    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [isOpen, refreshStatus, user?.tg_id]);

  const openTelegramBot = async (forceRefresh = false) => {
    const data = forceRefresh ? await loadLinkInfo() : (linkInfo || await loadLinkInfo());
    if (!data?.deep_link) {
      setError(lang === "en" ? "Telegram link is not ready yet" : "Ссылка на Telegram пока не готова");
      return;
    }

    let commandCopied = false;
    if (data.link_command && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(data.link_command);
        commandCopied = true;
      } catch (e) {
        console.error(e);
      }
    }

    const popup = window.open(data.deep_link, "_blank", "noopener,noreferrer");
    if (!popup) {
      window.location.href = data.deep_link;
    }

    setCopied(commandCopied);
    setHint(
      commandCopied
        ? (lang === "en"
            ? "Bot opened. If Telegram only opens the chat, paste the copied /link command and send it."
            : "Бот открыт. Если Telegram просто открыл чат, вставь скопированную команду /link и отправь её.")
        : (lang === "en"
            ? "Bot opened. If nothing happened, return here and refresh the status."
            : "Бот открыт. Если ничего не произошло, вернись сюда и обнови статус.")
    );
  };

  const handlePrimaryAction = async () => {
    if (user?.tg_id) {
      const unlinked = await unlinkTelegram();
      if (!unlinked) {
        return;
      }
      setHint(
        lang === "en"
          ? "Previous Telegram binding has been removed. Continue in Telegram to link again."
          : "Старая привязка снята. Продолжи в Telegram, чтобы привязать аккаунт заново."
      );
      setCopied(false);
      setLinkInfo(null);
    }

    await openTelegramBot(Boolean(user?.tg_id));
  };

  const botHandle = `@${linkInfo?.bot_username || "luggify_bot"}`;
  const telegramUsername = user?.social_links?.telegram
    ? user.social_links.telegram.replace(/^@/, "")
    : "";
  const telegramStatus = user?.tg_id
    ? (telegramUsername
        ? `@${telegramUsername}`
        : (lang === "en" ? "Connected" : "Подключен"))
    : (lang === "en" ? "Connect bot" : "Подключить бота");

  if (!user || !token) {
    return null;
  }

  return (
    <>
      <button
        className={`navbar-telegram-btn ${user?.tg_id ? "linked" : ""} ${buttonClassName}`.trim()}
        onClick={openModal}
        title={user?.tg_id
          ? (lang === "en" ? "Telegram connected" : "Telegram подключен")
          : (lang === "en" ? "Link Telegram" : "Привязать Telegram")}
        >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
        {!hideLabel && (
          menuMode ? (
            <span className="navbar-mobile-menu-copy">
              <strong>Telegram</strong>
              <span>{telegramStatus}</span>
            </span>
          ) : (
            <span className="navbar-telegram-label">Telegram</span>
          )
        )}
      </button>

      {isOpen && (
        <div className="modal-overlay modal-overlay-lifted telegram-modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="modal-content telegram-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setIsOpen(false)}>×</button>

            <div className="telegram-modal-head">
              <div className={`telegram-modal-badge ${user?.tg_id ? "linked" : ""}`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </div>
              <div>
                <h3 className="telegram-modal-title">Telegram</h3>
                <p className="telegram-modal-subtitle">
                  {user?.tg_id
                    ? (lang === "en"
                        ? "Account is already linked. You can reopen the bot or relink it."
                        : "Аккаунт уже связан. Можно открыть бота или перепривязать его.")
                    : (lang === "en"
                        ? "Link your site account with the bot so trips, AI and reminders work together."
                        : "Свяжи сайт и бота, чтобы поездки, AI и напоминания работали вместе.")}
                </p>
              </div>
            </div>

            <div className={`telegram-modal-status ${user?.tg_id ? "linked" : ""}`}>
              <span className="telegram-modal-status-label">
                {user?.tg_id
                  ? (lang === "en" ? "Status" : "Статус")
                  : (lang === "en" ? "Ready to link" : "Готово к привязке")}
              </span>
              <strong className="telegram-modal-status-value">
                {user?.tg_id
                  ? (telegramUsername
                      ? `@${telegramUsername}`
                      : (lang === "en" ? "Telegram is connected" : "Telegram подключен"))
                  : (lang === "en" ? "Not linked yet" : "Пока не привязан")}
              </strong>
            </div>

            <div className="telegram-modal-actions">
              <button className="telegram-modal-btn primary" onClick={handlePrimaryAction} disabled={loading}>
                {loading
                  ? "..."
                  : user?.tg_id
                    ? (lang === "en" ? "Relink Telegram" : "Перепривязать")
                    : (lang === "en" ? "Open bot" : "Открыть бота")}
              </button>
              <button className="telegram-modal-btn secondary" onClick={refreshStatus} disabled={loading}>
                {lang === "en" ? "Refresh status" : "Проверить статус"}
              </button>
            </div>

            {!user?.tg_id && (
              <div className="telegram-modal-note">
                {hint
                  ? hint
                  : (lang === "en"
                      ? `Open ${botHandle}. If Telegram does not trigger linking automatically, paste the /link command that we copy for you.`
                      : `Открой ${botHandle}. Если Telegram не запустит привязку сам, просто вставь команду /link, которую мы скопируем за тебя.`)}
              </div>
            )}

            {copied && !user?.tg_id && (
              <div className="telegram-modal-expiry">
                {lang === "en" ? "The /link command has been copied." : "Команда /link уже скопирована."}
              </div>
            )}

            {error && <div className="telegram-modal-error">{error}</div>}
          </div>
        </div>
      )}
    </>
  );
};

// === Sub-components for travel services ===

const TravelSectionShell = React.memo(({
  sectionKey,
  title,
  icon,
  children,
  defaultExpanded = true,
  actions = null,
  summary = "",
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const sectionClass = sectionKey ? ` travel-section-${String(sectionKey).split("-")[0]}` : "";

  useEffect(() => {
    setExpanded(defaultExpanded);
  }, [defaultExpanded, sectionKey]);

  return (
    <div className={`travel-section travel-section-shell${sectionClass}${expanded ? " expanded" : " collapsed"}`}>
      <div className="travel-section-header">
        <button
          type="button"
          className="travel-section-trigger"
          onClick={() => setExpanded((prev) => !prev)}
        >
          <span className="travel-section-title-wrap">
            <span className="travel-section-title-icon">{icon}</span>
            <span className="travel-section-title-copy">
              <span className="travel-section-title-text">{title}</span>
              {!expanded && summary && (
                <span className="travel-section-summary">{summary}</span>
              )}
            </span>
          </span>
        </button>
        <div className="travel-section-header-actions">
          {actions}
          <button
            type="button"
            className="collapse-toggle"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
          >
            <span className={`chevron ${expanded ? "up" : ""}`}>▾</span>
          </button>
        </div>
      </div>
      {expanded && <div className="travel-section-body">{children}</div>}
    </div>
  );
});

const ATTRACTION_CROP_ASPECT = 4 / 5;
const ATTRACTION_CROP_OUTPUT_WIDTH = 960;
const ATTRACTION_CROP_OUTPUT_HEIGHT = Math.round(ATTRACTION_CROP_OUTPUT_WIDTH / ATTRACTION_CROP_ASPECT);
const clampAttractionValue = (value, min, max) => Math.min(Math.max(value, min), max);

const getAttractionDisplayLayout = (stageSize, imageMeta, cropScale = 0.6) => {
  if (!stageSize?.width || !stageSize?.height || !imageMeta?.width || !imageMeta?.height) {
    return null;
  }

  const baseScale = Math.min(
    stageSize.width / imageMeta.width,
    stageSize.height / imageMeta.height
  );
  const scale = baseScale || 1;
  const displayWidth = imageMeta.width * scale;
  const displayHeight = imageMeta.height * scale;
  const offsetX = (stageSize.width - displayWidth) / 2;
  const offsetY = (stageSize.height - displayHeight) / 2;

  let maxCropWidth = displayWidth;
  let maxCropHeight = maxCropWidth / ATTRACTION_CROP_ASPECT;
  if (maxCropHeight > displayHeight) {
    maxCropHeight = displayHeight;
    maxCropWidth = maxCropHeight * ATTRACTION_CROP_ASPECT;
  }

  const safeCropScale = clampAttractionValue(cropScale || 0.6, 0.2, 1);
  const cropWidth = maxCropWidth * safeCropScale;
  const cropHeight = maxCropHeight * safeCropScale;

  return {
    displayWidth,
    displayHeight,
    offsetX,
    offsetY,
    cropWidth,
    cropHeight,
    stageWidth: stageSize.width,
    stageHeight: stageSize.height,
  };
};

const getAttractionClampedCropCenter = (center, layout) => {
  if (!layout) return { x: 0.5, y: 0.5 };

  const halfWidthRatio = (layout.cropWidth / 2) / layout.displayWidth;
  const halfHeightRatio = (layout.cropHeight / 2) / layout.displayHeight;

  return {
    x: clampAttractionValue(center?.x ?? 0.5, halfWidthRatio, 1 - halfWidthRatio),
    y: clampAttractionValue(center?.y ?? 0.5, halfHeightRatio, 1 - halfHeightRatio),
  };
};

const getAttractionCropRect = (layout, center) => {
  if (!layout) return null;
  const safeCenter = getAttractionClampedCropCenter(center, layout);
  return {
    left: layout.offsetX + (safeCenter.x * layout.displayWidth) - (layout.cropWidth / 2),
    top: layout.offsetY + (safeCenter.y * layout.displayHeight) - (layout.cropHeight / 2),
    width: layout.cropWidth,
    height: layout.cropHeight,
    center: safeCenter,
  };
};

const buildAttractionProxyUrl = (imageUrl) => `${API_URL}/attractions/image-proxy?url=${encodeURIComponent(imageUrl)}`;

const buildMapsPlaceUrl = ({ lang = "ru", query = "", lat = null, lng = null } = {}) => {
  const normalizedLat = Number(lat);
  const normalizedLng = Number(lng);
  const hasCoords = Number.isFinite(normalizedLat) && Number.isFinite(normalizedLng);
  const safeQuery = String(query || "").trim();
  const fallbackQuery = hasCoords ? `${normalizedLat},${normalizedLng}` : safeQuery;

  if (lang === "en") {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(safeQuery || fallbackQuery)}`;
  }

  const text = encodeURIComponent(safeQuery || fallbackQuery);
  if (hasCoords) {
    return `https://yandex.ru/maps/?text=${text}&ll=${normalizedLng},${normalizedLat}&z=16`;
  }
  return `https://yandex.ru/maps/?text=${text}`;
};

const getMapsPlaceLabel = (lang = "ru") => (lang === "en" ? "Open map" : "На карте");

const AttractionsCityBlock = React.memo(({ city, lang, limit, user, token }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [savingImageIndex, setSavingImageIndex] = useState(null);
  const [adminImageModal, setAdminImageModal] = useState(null);
  const [adminImageUrlInput, setAdminImageUrlInput] = useState("");
  const [adminImageSource, setAdminImageSource] = useState(null);
  const [adminImageLoading, setAdminImageLoading] = useState(false);
  const [adminImageError, setAdminImageError] = useState("");
  const [adminImageMeta, setAdminImageMeta] = useState(null);
  const [adminImageStageSize, setAdminImageStageSize] = useState({ width: 0, height: 0 });
  const [adminCropScale, setAdminCropScale] = useState(0.72);
  const [adminCropCenter, setAdminCropCenter] = useState({ x: 0.5, y: 0.5 });
  const adminImageStageRef = useRef(null);
  const adminImageElementRef = useRef(null);
  const adminImageFileInputRef = useRef(null);
  const adminCropDragRef = useRef(null);

  useEffect(() => {
    if (!city) return;
    setLoading(true);
    setLoaded(false);
    fetch(`${API_URL}/attractions?city=${encodeURIComponent(city)}&lang=${lang}&limit=${limit}`)
      .then(r => r.json())
      .then(d => setData(d.attractions || []))
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [city, lang, limit]);

  useEffect(() => {
    setAdminImageModal(null);
  }, [city, lang, limit]);

  useEffect(() => {
    if (!adminImageModal) return undefined;

    const updateStageSize = () => {
      const node = adminImageStageRef.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      setAdminImageStageSize((current) => {
        const nextSize = {
          width: Math.max(0, rect.width),
          height: Math.max(0, rect.height),
        };
        if (current.width === nextSize.width && current.height === nextSize.height) {
          return current;
        }
        return nextSize;
      });
    };

    const frameId = window.requestAnimationFrame(updateStageSize);
    const resizeObserver = typeof ResizeObserver !== "undefined"
      ? new ResizeObserver(updateStageSize)
      : null;
    if (resizeObserver && adminImageStageRef.current) {
      resizeObserver.observe(adminImageStageRef.current);
    }
    window.addEventListener("resize", updateStageSize);
    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", updateStageSize);
    };
  }, [adminImageModal, adminImageSource?.previewSrc]);

  useEffect(() => {
    if (!adminImageModal) return undefined;

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [adminImageModal]);

  const adminDisplayLayout = getAttractionDisplayLayout(adminImageStageSize, adminImageMeta, adminCropScale);
  const adminCropRect = getAttractionCropRect(adminDisplayLayout, adminCropCenter);
  const adminStageHeight = adminImageMeta && adminImageStageSize.width
    ? clampAttractionValue(
      adminImageStageSize.width / (adminImageMeta.width / adminImageMeta.height),
      260,
      620
    )
    : null;

  useEffect(() => {
    if (!adminImageModal || !adminCropDragRef.current) return undefined;

    const handlePointerMove = (event) => {
      const dragState = adminCropDragRef.current;
      if (!dragState || !adminDisplayLayout) return;
      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;
      setAdminCropCenter(getAttractionClampedCropCenter({
        x: dragState.startCenter.x + (deltaX / adminDisplayLayout.displayWidth),
        y: dragState.startCenter.y + (deltaY / adminDisplayLayout.displayHeight),
      }, adminDisplayLayout));
    };

    const handlePointerUp = () => {
      adminCropDragRef.current = null;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [adminImageModal, adminDisplayLayout]);

  useEffect(() => {
    if (!adminDisplayLayout) return;
    setAdminCropCenter((current) => getAttractionClampedCropCenter(current, adminDisplayLayout));
  }, [
    adminDisplayLayout?.displayWidth,
    adminDisplayLayout?.displayHeight,
    adminDisplayLayout?.cropWidth,
    adminDisplayLayout?.cropHeight,
    adminDisplayLayout?.offsetX,
    adminDisplayLayout?.offsetY,
    adminDisplayLayout,
  ]);

  const resetAdminImageEditor = () => {
    setAdminImageUrlInput("");
    setAdminImageSource(null);
    setAdminImageLoading(false);
    setAdminImageError("");
    setAdminImageMeta(null);
    setAdminCropScale(0.72);
    setAdminCropCenter({ x: 0.5, y: 0.5 });
    setAdminImageStageSize({ width: 0, height: 0 });
    adminCropDragRef.current = null;
    if (adminImageFileInputRef.current) {
      adminImageFileInputRef.current.value = "";
    }
  };

  const closeAdminImageModal = () => {
    if (savingImageIndex !== null) return;
    setAdminImageModal(null);
    resetAdminImageEditor();
  };

  const openAdminImageModal = (event, attraction, index) => {
    event.preventDefault();
    event.stopPropagation();
    if (!token) return;

    setAdminImageModal({ attraction, index });
    setAdminImageError("");
    setAdminImageLoading(false);
    setAdminImageMeta(null);
    setAdminCropScale(0.72);
    setAdminCropCenter({ x: 0.5, y: 0.5 });

    const currentImage = String(attraction.image || "").trim();
    if (!currentImage) {
      setAdminImageUrlInput("");
      setAdminImageSource(null);
      return;
    }

    const isDataUrl = currentImage.startsWith("data:image/");
    setAdminImageUrlInput(isDataUrl ? "" : currentImage);
    setAdminImageSource({
      previewSrc: isDataUrl ? currentImage : buildAttractionProxyUrl(currentImage),
      originalSrc: currentImage,
      isDataUrl,
    });
  };

  const loadAdminImageFromUrl = async () => {
    const trimmedUrl = adminImageUrlInput.trim();
    if (!trimmedUrl) {
      setAdminImageError(lang === "en" ? "Paste an image URL first" : "Сначала вставь ссылку на картинку");
      return;
    }

    setAdminImageLoading(true);
    setAdminImageError("");
    setAdminImageMeta(null);
    setAdminCropScale(0.72);
    setAdminCropCenter({ x: 0.5, y: 0.5 });
    setAdminImageSource({
      previewSrc: buildAttractionProxyUrl(trimmedUrl),
      originalSrc: trimmedUrl,
      isDataUrl: false,
    });
  };

  const handleAdminImageFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setAdminImageError(lang === "en" ? "Choose an image file" : "Выбери файл-картинку");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const previewSrc = String(reader.result || "");
      setAdminImageLoading(false);
      setAdminImageError("");
      setAdminImageMeta(null);
      setAdminCropScale(0.72);
      setAdminCropCenter({ x: 0.5, y: 0.5 });
      setAdminImageSource({
        previewSrc,
        originalSrc: previewSrc,
        isDataUrl: true,
      });
    };
    reader.onerror = () => {
      setAdminImageError(lang === "en" ? "Could not read file" : "Не удалось прочитать файл");
    };
    reader.readAsDataURL(file);
  };

  const handleAdminImageLoaded = (event) => {
    setAdminImageLoading(false);
    setAdminImageError("");
    setAdminImageMeta({
      width: event.currentTarget.naturalWidth,
      height: event.currentTarget.naturalHeight,
    });
  };

  const handleAdminImageLoadError = () => {
    setAdminImageLoading(false);
    setAdminImageMeta(null);
    setAdminImageError(lang === "en" ? "Could not load image" : "Не удалось загрузить картинку");
  };

  const applyAdminCropScale = React.useCallback((nextScale) => {
    const normalizedScale = clampAttractionValue(nextScale, 0.24, 1);
    if (!adminImageMeta || !adminImageStageSize.width || !adminImageStageSize.height) {
      setAdminCropScale(normalizedScale);
      return;
    }

    const nextLayout = getAttractionDisplayLayout(adminImageStageSize, adminImageMeta, normalizedScale);
    setAdminCropScale(normalizedScale);
    setAdminCropCenter((current) => getAttractionClampedCropCenter(current, nextLayout));
  }, [adminImageMeta, adminImageStageSize]);

  useEffect(() => {
    const stageNode = adminImageStageRef.current;
    if (!adminImageModal || !stageNode) return undefined;

    const nativeWheelHandler = (event) => {
      if (!adminImageMeta) return;
      event.preventDefault();
      event.stopPropagation();
      const wheelStep = clampAttractionValue(event.deltaY * 0.00035, -0.014, 0.014);
      applyAdminCropScale(adminCropScale + wheelStep);
    };

    stageNode.addEventListener("wheel", nativeWheelHandler, { passive: false });
    return () => {
      stageNode.removeEventListener("wheel", nativeWheelHandler);
    };
  }, [adminCropScale, adminImageMeta, adminImageModal, adminImageStageSize.width, adminImageStageSize.height, applyAdminCropScale]);

  const handleAdminCropPointerDown = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!adminDisplayLayout) return;
    adminCropDragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      startCenter: adminCropRect?.center || { x: 0.5, y: 0.5 },
    };
  };

  const buildAdminCroppedImage = () => {
    const imageNode = adminImageElementRef.current;
    const layout = adminDisplayLayout;
    const cropRect = adminCropRect;

    if (!imageNode || !layout || !cropRect || !adminImageMeta) {
      throw new Error(lang === "en" ? "Load an image first" : "Сначала загрузи картинку");
    }

    const canvas = document.createElement("canvas");
    canvas.width = ATTRACTION_CROP_OUTPUT_WIDTH;
    canvas.height = ATTRACTION_CROP_OUTPUT_HEIGHT;
    const context = canvas.getContext("2d");
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    const sourceX = clampAttractionValue(
      ((cropRect.left - layout.offsetX) / layout.displayWidth) * adminImageMeta.width,
      0,
      adminImageMeta.width
    );
    const sourceY = clampAttractionValue(
      ((cropRect.top - layout.offsetY) / layout.displayHeight) * adminImageMeta.height,
      0,
      adminImageMeta.height
    );
    const sourceWidth = clampAttractionValue(
      (cropRect.width / layout.displayWidth) * adminImageMeta.width,
      1,
      adminImageMeta.width - sourceX
    );
    const sourceHeight = clampAttractionValue(
      (cropRect.height / layout.displayHeight) * adminImageMeta.height,
      1,
      adminImageMeta.height - sourceY
    );
    context.drawImage(
      imageNode,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      0,
      0,
      canvas.width,
      canvas.height
    );

    return canvas.toDataURL("image/jpeg", 0.9);
  };

  const handleAdminImageSave = async () => {
    if (!token || !adminImageModal) return;

    setSavingImageIndex(adminImageModal.index);
    setAdminImageError("");

    try {
      const croppedImage = buildAdminCroppedImage();
      const attraction = adminImageModal.attraction;
      const response = await fetch(`${API_URL}/attractions/image`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          city,
          lang,
          limit,
          attraction_name: attraction.name,
          attraction_link: attraction.link || null,
          image: croppedImage,
        }),
      });

      const responseData = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(responseData.detail || (lang === "en" ? "Could not save image" : "Не удалось сохранить картинку"));
      }

      if (Array.isArray(responseData.attractions)) {
        setData(responseData.attractions);
      } else {
        setData((prev) => prev.map((item, itemIndex) => (
          itemIndex === adminImageModal.index
            ? { ...item, image: croppedImage, image_source: "admin", admin_image: true }
            : item
        )));
      }

      closeAdminImageModal();
    } catch (error) {
      setAdminImageError(error.message || (lang === "en" ? "Could not save image" : "Не удалось сохранить картинку"));
    } finally {
      setSavingImageIndex(null);
    }
  };

  if (loaded && data.length === 0) return null;
  if (!loaded && !loading) return null;

  return (
    <>
      {loading ? (
        <div className="section-loading">
          <div className="loading-spinner-wrap">
            <div className="loading-spinner" />
            <span className="loading-text">{TRANSLATIONS[lang].searchingAttractions}</span>
          </div>
        </div>
      ) : (
        <div className="attractions-grid">
          {data.map((a, i) => (
            <div key={i} className="attraction-card">
              <a href={lang === 'ru' ? `https://yandex.ru/search/?text=${encodeURIComponent(a.name + ' ' + city)}` : `https://www.google.com/search?q=${encodeURIComponent(a.name + ' ' + city)}`} target="_blank" rel="noopener noreferrer" className="attraction-bg-link">
                {a.image && (
                  <img
                    src={a.image}
                    alt={a.name}
                    className="attraction-img"
                    loading="lazy"
                    style={{ objectPosition: a.image_position || "center center" }}
                  />
                )}
                <div className="attraction-body">
                  <div className="attraction-name">{a.name}</div>
                </div>
              </a>
              <a
                className="attraction-map-btn"
                href={buildMapsPlaceUrl({
                  lang,
                  query: `${a.name} ${city}`,
                  lat: a.lat,
                  lng: a.lng,
                })}
                target="_blank"
                rel="noopener noreferrer"
                title={getMapsPlaceLabel(lang)}
                aria-label={getMapsPlaceLabel(lang)}
                onClick={(event) => event.stopPropagation()}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </a>
              {user?.is_admin && (
                <button
                  type="button"
                  className="attraction-admin-image-btn"
                  onClick={(event) => openAdminImageModal(event, a, i)}
                  disabled={savingImageIndex === i}
                  title={lang === "en" ? "Edit card image" : "Настроить картинку карточки"}
                >
                  {savingImageIndex === i ? "..." : (lang === "en" ? "Photo" : "Фото")}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {user?.is_admin && adminImageModal && (
        <div className="modal-overlay" onClick={closeAdminImageModal}>
          <div className="modal-content attraction-crop-modal" onClick={(event) => event.stopPropagation()}>
            <button type="button" className="modal-close" onClick={closeAdminImageModal}>&times;</button>
            <div className="attraction-crop-modal-head">
              <span>{lang === "en" ? "Card image" : "Картинка карточки"}</span>
              <h3>{adminImageModal.attraction?.name}</h3>
            </div>

            <div className="attraction-crop-modal-layout">
              <div className="attraction-crop-stage-wrap">
                <div
                  ref={adminImageStageRef}
                  className="attraction-crop-stage"
                  style={adminStageHeight ? { height: `${adminStageHeight}px` } : undefined}
                >
                  {!adminImageSource && (
                    <div className="attraction-crop-placeholder">
                      {lang === "en" ? "Load an image to start framing it." : "Загрузи картинку, и здесь появится область кадрирования."}
                    </div>
                  )}

                  {adminImageLoading && (
                    <div className="attraction-crop-placeholder">
                      {lang === "en" ? "Loading image..." : "Загружаю картинку..."}
                    </div>
                  )}

                  {adminImageSource && (
                    <img
                      ref={adminImageElementRef}
                      src={adminImageSource.previewSrc}
                      alt=""
                      className="attraction-crop-image"
                      style={{
                        width: `${adminDisplayLayout?.displayWidth || 0}px`,
                        height: `${adminDisplayLayout?.displayHeight || 0}px`,
                        left: `${adminDisplayLayout?.offsetX || 0}px`,
                        top: `${adminDisplayLayout?.offsetY || 0}px`,
                      }}
                      onLoad={handleAdminImageLoaded}
                      onError={handleAdminImageLoadError}
                      crossOrigin="anonymous"
                    />
                  )}

                  {adminCropRect && (
                    <div
                      className="attraction-crop-box"
                      style={{
                        left: `${adminCropRect.left}px`,
                        top: `${adminCropRect.top}px`,
                        width: `${adminCropRect.width}px`,
                        height: `${adminCropRect.height}px`,
                      }}
                      onPointerDown={handleAdminCropPointerDown}
                    >
                      <span />
                    </div>
                  )}
                </div>
              </div>

              <div className="attraction-crop-controls">
                <label className="attraction-crop-field">
                  <span>{lang === "en" ? "Image URL" : "Ссылка на картинку"}</span>
                  <div className="attraction-crop-link-row">
                    <input
                      type="url"
                      value={adminImageUrlInput}
                      onChange={(event) => setAdminImageUrlInput(event.target.value)}
                      placeholder="https://..."
                    />
                    <button
                      type="button"
                      className="action-btn attraction-crop-inline-btn"
                      onClick={loadAdminImageFromUrl}
                      disabled={adminImageLoading}
                    >
                      {lang === "en" ? "Load" : "Загрузить"}
                    </button>
                  </div>
                </label>

                <div className="attraction-crop-divider">{lang === "en" ? "or" : "или"}</div>

                <input
                  ref={adminImageFileInputRef}
                  type="file"
                  accept="image/*"
                  className="attraction-crop-file-input"
                  onChange={handleAdminImageFileChange}
                />
                <button
                  type="button"
                  className="action-btn"
                  onClick={() => adminImageFileInputRef.current?.click()}
                >
                  {lang === "en" ? "Choose file" : "Выбрать файл"}
                </button>

                <label className="attraction-crop-field">
                  <span>{lang === "en" ? "Frame size" : "Размер области"}</span>
                  <input
                    type="range"
                    min="0.24"
                    max="1"
                    step="0.05"
                    value={adminCropScale}
                    onChange={(event) => applyAdminCropScale(Number(event.target.value))}
                    disabled={!adminImageSource}
                  />
                </label>

                <p className="attraction-crop-help">
                  {lang === "en"
                    ? "The full image stays open. Drag the frame with the left mouse button, and use the mouse wheel to change its size."
                    : "Картинка открыта целиком. Зажми левую кнопку мыши и двигай рамку по изображению, а колесиком меняй размер области."}
                </p>

                {adminImageError && <div className="telegram-modal-error attraction-crop-error">{adminImageError}</div>}

                <div className="attraction-crop-actions">
                  <button type="button" className="action-btn" onClick={closeAdminImageModal}>
                    {lang === "en" ? "Cancel" : "Отмена"}
                  </button>
                  <button
                    type="button"
                    className="action-btn primary"
                    onClick={handleAdminImageSave}
                    disabled={savingImageIndex === adminImageModal.index || !adminCropRect}
                  >
                    {savingImageIndex === adminImageModal.index
                      ? "..."
                      : (lang === "en" ? "Save crop" : "Сохранить кадр")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
});

const AttractionsSection = React.memo(({ city, lang, compact = false, user, token }) => {
  const citiesList = city ? (city.includes(" + ") ? city.split(" + ").map(c => c.trim()) : [city]) : [];
  const primaryCity = citiesList[0] || "";
  const [activeCity, setActiveCity] = useState(primaryCity);
  const limit = citiesList.length > 1 ? 5 : 10;
  const sectionSummary = compact
    ? `${citiesList.length > 1 ? citiesList.length : limit} ${lang === "en" ? "spots" : "мест"}`
    : "";

  useEffect(() => {
    setActiveCity(primaryCity);
  }, [primaryCity]);

  if (!city) return null;

  return (
    <TravelSectionShell
      sectionKey={`attractions-${city}-${lang}-${compact ? "compact" : "full"}`}
      title={TRANSLATIONS[lang].whatToSee}
      icon={<MuseumIcon />}
      defaultExpanded={!compact}
      summary={sectionSummary}
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      <div key={activeCity}>
        <AttractionsCityBlock city={activeCity} lang={lang} limit={limit} user={user} token={token} />
      </div>
      <div style={{ display: "flex", justifyContent: "center", marginTop: "1rem" }}>
        <a
          href={`https://www.google.com/search?q=${encodeURIComponent((lang === "ru" ? "Достопримечательности " : "Attractions ") + activeCity.split(",")[0])}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flights-search-btn"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
          {TRANSLATIONS[lang].showMoreAttractions || "Показать больше"}
        </a>
      </div>
    </TravelSectionShell>
  );
});

const TripPartyEditor = React.memo(({
  value,
  onChange,
  lang,
  readOnly = false,
  className = "",
}) => {
  const party = normalizeTripParty(value);
  const { adults, children_ages: childrenAges, child_profiles: childProfiles } = party;
  const isRu = lang !== "en";
  const applyPatch = (patch) => {
    if (!onChange || readOnly) return;
    onChange({
      ...party,
      ...patch,
    });
  };

  const setChildrenCount = (nextCount) => {
    const nextChildrenAges = resizeChildrenAges(childrenAges, nextCount);
    applyPatch({
      children_ages: nextChildrenAges,
      child_profiles: normalizeChildProfiles(childProfiles, nextChildrenAges),
    });
  };

  const setChildAge = (index, nextAge) => {
    const nextChildrenAges = [...childrenAges];
    nextChildrenAges[index] = Number.parseInt(nextAge, 10);
    const normalizedAges = normalizeChildrenAges(nextChildrenAges);
    applyPatch({
      children_ages: normalizedAges,
      child_profiles: normalizeChildProfiles(childProfiles, normalizedAges),
    });
  };

  const setChildName = (index, nextName) => {
    const nextProfiles = normalizeChildProfiles(childProfiles, childrenAges);
    nextProfiles[index] = {
      ...nextProfiles[index],
      name: nextName.slice(0, 40),
    };
    applyPatch({ child_profiles: nextProfiles });
  };

  return (
    <div className={`trip-party-editor ${className}`.trim()}>
      <div className="guest-row">
        <div className="guest-info">
          <span className="guest-label">{isRu ? "Взрослые" : "Adults"}</span>
          <span className="guest-label-note">{isRu ? "18 лет и старше" : "18 years and older"}</span>
        </div>
        <div className="guest-controls">
          <button type="button" onClick={() => applyPatch({ adults: Math.max(1, adults - 1) })} className="guest-control-btn" disabled={readOnly || adults <= 1}>-</button>
          <span className="guest-value">{adults}</span>
          <button type="button" onClick={() => applyPatch({ adults: adults + 1 })} className="guest-control-btn" disabled={readOnly}>+</button>
        </div>
      </div>

      <div className="guest-row">
        <div className="guest-info">
          <span className="guest-label">{isRu ? "Дети" : "Children"}</span>
        </div>
        <div className="guest-controls">
          <button type="button" onClick={() => setChildrenCount(childrenAges.length - 1)} className="guest-control-btn" disabled={readOnly || childrenAges.length === 0}>-</button>
          <span className="guest-value">{childrenAges.length}</span>
          <button type="button" onClick={() => setChildrenCount(childrenAges.length + 1)} className="guest-control-btn" disabled={readOnly || childrenAges.length >= 8}>+</button>
        </div>
      </div>

      {childrenAges.length > 0 && (
        <div className="children-ages-wrap">
          {childrenAges.map((age, index) => (
            <div key={`child-${index}`} className="child-age-card">
              <div className="child-age-copy">
                <span className="child-age-label">{isRu ? `Ребенок ${index + 1}` : `Child ${index + 1}`}</span>
                <input
                  className="child-name-input"
                  type="text"
                  value={childProfiles[index]?.name || ""}
                  onChange={(event) => setChildName(index, event.target.value)}
                  placeholder={isRu ? "Имя" : "Name"}
                  disabled={readOnly}
                />
              </div>
              <div className="child-age-inline-controls">
                <button
                  type="button"
                  className="child-age-stepper"
                  onClick={() => setChildAge(index, Math.max(0, age - 1))}
                  disabled={readOnly || age <= 0}
                >
                  -
                </button>
                <div className="child-age-current">{age} {isRu ? "лет" : "y.o."}</div>
                <button
                  type="button"
                  className="child-age-stepper"
                  onClick={() => setChildAge(index, Math.min(17, age + 1))}
                  disabled={readOnly || age >= 17}
                >
                  +
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

const FlightsSection = React.memo(({ city, startDate, origin, returnDate, lang, compact = false, tripProfile = null }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [flightClass, setFlightClass] = useState("0");

  const [genericLink, setGenericLink] = useState("");
  const [flightSearchLinks, setFlightSearchLinks] = useState({ outbound: "", inbound: "" });
  const passengerCounts = getFlightPassengerCounts(tripProfile || {});
  const flightClassOptions = getFlightClassOptions(lang);
  const selectedFlightClassLabel = flightClassOptions.find((option) => option.value === flightClass)?.label || flightClassOptions[0]?.label || "";
  const isGroupSearch = passengerCounts.adults + passengerCounts.children + passengerCounts.infants > 1;
  const isEconomyClass = flightClass === "0";

  useEffect(() => {
    if (!city) return;
    setLoading(true);
    setLoaded(false);
    const params = new URLSearchParams({ destination: city });
    if (startDate) params.append("date", startDate);
    if (origin) params.append("origin", origin);
    if (returnDate) params.append("return_date", returnDate);
    params.append("adults", String(passengerCounts.adults));
    params.append("children", String(passengerCounts.children));
    params.append("infants", String(passengerCounts.infants));
    params.append("trip_class", flightClass);
    fetch(`${API_URL}/flights/search?${params}`)
      .then(r => r.json())
      .then(d => {
        setData(d.flights || []);
        setGenericLink(d.generic_link || "");
        setFlightSearchLinks({
          outbound: d.outbound_link || "",
          inbound: d.inbound_link || "",
        });
      })
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [city, startDate, origin, returnDate, passengerCounts.adults, passengerCounts.children, passengerCounts.infants, flightClass]);

  if (loaded && data.length === 0 && !genericLink) return null;
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  const renderFlightCard = (f, key) => (
    <a key={key} href={f.link} target="_blank" rel="noopener noreferrer" className="flight-card" style={{ height: "100%" }}>
      {f.tag && <div className="flight-tag">{translateFlightTagLabel(f.tag, lang)}</div>}
      <div className="flight-price">
        {f.price ? `${f.price.toLocaleString(formatChecklistLocale(lang))} ₽` : t.priceOnRequest}
        {f.price && isGroupSearch && <span className="flight-price-note">{t.flightPricePerPassenger}</span>}
      </div>
      <div className="flight-route">
        {f.origin_label || f.origin} → {f.destination_label || f.destination}
      </div>
      {f.airline && (
        <div className="flight-airline">
          <PlaneIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-1px' }} />
          <span>{translateAirlineLabel(f.airline_name || f.airline, lang)}</span>
        </div>
      )}
      <div className="flight-info">
        <span>{f.transfers === 0 ? t.directFlight : pluralize(f.transfers, ['пересадка', 'пересадки', 'пересадок'], ['stop', 'stops'], lang)}</span>
        {f.duration > 0 && <span style={{ display: 'inline-flex', alignItems: 'center' }}><ClockIcon style={{ width: '16px', height: '16px', marginRight: '4px', marginTop: '-1px' }} /> {formatDuration(f.duration, lang)}</span>}
        {f.departure_at && (
          <span className="flight-date-inline">
            {new Date(f.departure_at).toLocaleDateString(formatChecklistLocale(lang), { day: "numeric", month: "short" })}
          </span>
        )}
      </div>
    </a>
  );

  return (
    <TravelSectionShell
      sectionKey={`flights-${city}-${startDate || ""}-${returnDate || ""}-${compact ? "compact" : "full"}`}
      title={t.flightsTitle}
      icon={<PlaneIcon />}
      defaultExpanded={!compact}
      summary={loading ? (lang === "en" ? "Loading" : "Загружается") : formatTripPartySummary(tripProfile || {}, lang)}
    >
      <div className="flight-class-picker" aria-label={t.flightClassLabel}>
        <span className="flight-class-label">{t.flightClassLabel}</span>
        <div className="flight-class-options">
          {flightClassOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`flight-class-chip ${flightClass === option.value ? "active" : ""}`}
              onClick={() => setFlightClass(option.value)}
              disabled={loading}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="loading-spinner-wrap">
          <div className="loading-spinner" />
          <span className="loading-text">{t.searchingFlights}</span>
        </div>
      ) : (
        <>
          {!isEconomyClass && (
            <div className="flight-class-search-panel">
              <div className="flights-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                {flightSearchLinks.outbound && (
                  <a href={flightSearchLinks.outbound} target="_blank" rel="noopener noreferrer" className="flight-card flight-search-card">
                    <div className="flight-search-card-top">
                      <span className="flight-search-pill">{selectedFlightClassLabel}</span>
                      <span className="flight-search-arrow">→</span>
                    </div>
                    <div className="flight-search-title">{t.outboundFlights}</div>
                    <div className="flight-search-cta">{lang === "en" ? "Open search" : "Открыть поиск"}</div>
                  </a>
                )}
                {flightSearchLinks.inbound && (
                  <a href={flightSearchLinks.inbound} target="_blank" rel="noopener noreferrer" className="flight-card flight-search-card">
                    <div className="flight-search-card-top">
                      <span className="flight-search-pill">{selectedFlightClassLabel}</span>
                      <span className="flight-search-arrow">→</span>
                    </div>
                    <div className="flight-search-title">{t.inboundFlights}</div>
                    <div className="flight-search-cta">{lang === "en" ? "Open search" : "Открыть поиск"}</div>
                  </a>
                )}
              </div>
            </div>
          )}
          {data.length > 0 && (
            <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
              {data.filter(f => f.type === "outbound" || !f.type).length > 0 && (
                <div style={{ flex: "1 1 300px" }}>
                  <h4 style={{ margin: "0 0 0.75rem 0", color: "#9ca3af", fontSize: "0.95rem", fontWeight: "600" }}>{t.outboundFlights}</h4>
                  <div className="flights-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                    {data.filter(f => f.type === "outbound" || !f.type).map((f, i) => (
                      renderFlightCard(f, `out-${i}`)
                    ))}
                  </div>
                </div>
              )}
              {data.filter(f => f.type === "inbound").length > 0 && (
                <div style={{ flex: "1 1 300px" }}>
                  <h4 style={{ margin: "0 0 0.75rem 0", color: "#9ca3af", fontSize: "0.95rem", fontWeight: "600" }}>{t.inboundFlights}</h4>
                  <div className="flights-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                    {data.filter(f => f.type === "inbound").map((f, i) => (
                      renderFlightCard(f, `in-${i}`)
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {isEconomyClass && data.length === 0 && genericLink && (
            <div style={{ marginBottom: "1rem", textAlign: "center", color: "#9ca3af" }}>
              {t.noCachedTickets}<br /><br />
            </div>
          )}
          {genericLink && (
            <div style={{ display: "flex", justifyContent: "center", width: "100%", marginTop: "1rem" }}>
              <a href={genericLink} target="_blank" rel="noopener noreferrer" className="flights-search-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                {t.searchReturnTickets}
              </a>
            </div>
          )}
        </>
      )}
    </TravelSectionShell>
  );
});

const HotelsSection = React.memo(({ city, startDate, endDate, lang, compact = false, tripProfile = null }) => {
  const citiesList = city ? city.split("+").map(c => c.trim()) : [];
  const primaryCity = citiesList[0] || "";
  const [activeCity, setActiveCity] = useState(primaryCity);

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [triggered, setTriggered] = useState(false);

  const [provider, setProvider] = useState(null);
  const [links, setLinks] = useState({});
  const { adults } = getTripPartyCounts(tripProfile || {});
  const childrenAges = buildHotelChildrenAges(tripProfile || {});
  const travelersCount = adults + childrenAges.length;
  const roomLimit = Math.max(1, Math.min(travelersCount, 8));
  const [hotelRooms, setHotelRooms] = useState(1);
  const [hotelRating, setHotelRating] = useState(0);
  const [hotelPriceMin, setHotelPriceMin] = useState("");
  const [hotelPriceMax, setHotelPriceMax] = useState("");
  const [hotelMinBedrooms, setHotelMinBedrooms] = useState(0);
  const normalizedHotelRooms = normalizeHotelRoomsCount(hotelRooms, travelersCount);
  const accommodationPlan = buildAccommodationUnitPlan({
    adults,
    childrenAges,
    units: normalizedHotelRooms,
  });
  const showRoomsControl = travelersCount > 1;
  const normalizedHotelRating = normalizeHotelRating(hotelRating);
  const normalizedHotelPriceMin = normalizeHotelPriceValue(hotelPriceMin);
  const normalizedHotelPriceMax = normalizeHotelPriceValue(hotelPriceMax);
  const normalizedHotelMinBedrooms = normalizeHotelBedroomsValue(hotelMinBedrooms);
  const passengerSignature = `${adults}:${childrenAges.join(",")}:${normalizedHotelRooms}:${normalizedHotelRating}:${normalizedHotelPriceMin}:${normalizedHotelPriceMax}:${normalizedHotelMinBedrooms}`;
  const lastPassengerSignatureRef = useRef(passengerSignature);
  const hotelCurrency = lang === "en" ? "USD" : "RUB";
  const hotelLocale = lang === "en" ? "en-us" : "ru";

  const doFetch = () => {
    if (!activeCity) return;
    setLoading(true);
    setLoaded(false);
    setTriggered(true);
    const params = new URLSearchParams({ city: activeCity, adults });
    params.append("rooms", String(normalizedHotelRooms));
    if (startDate) params.append("check_in", startDate);
    if (endDate) params.append("check_out", endDate);
    if (childrenAges.length > 0) params.append("children_ages", childrenAges.join(","));
    if (normalizedHotelRating > 0) params.append("review_score", String(normalizedHotelRating));
    if (normalizedHotelPriceMin) params.append("price_min", normalizedHotelPriceMin);
    if (normalizedHotelPriceMax) params.append("price_max", normalizedHotelPriceMax);
    if (normalizedHotelMinBedrooms > 0) params.append("min_bedrooms", String(normalizedHotelMinBedrooms));
    params.append("currency", hotelCurrency);
    params.append("locale", hotelLocale);
    fetch(`${API_URL}/hotels/search?${params}&limit_per_city=${citiesList.length > 1 ? 5 : 10}`)
      .then(r => r.json())
      .then(d => {
        setData(d.hotels || []);
        setProvider(d.provider || null);
        setLinks(d.links || {});
      })
      .catch(() => setData([]))
      .finally(() => { setLoading(false); setLoaded(true); });
  };

  const cLower = activeCity ? activeCity.toLowerCase() : "";
  const ruCities = [
    "москва", "санкт-петербург", "питер", "спб", "сочи", "казань",
    "новосибирск", "екатеринбург", "нижний новгород", "краснодар",
    "калининград", "владивосток", "анапа", "геленджик", "адлер"
  ];
  const isRussia = cLower.includes("россия") || cLower.includes("russia") || ruCities.some(rc => cLower.includes(rc));

  const childrenQuery = childrenAges.length > 0 ? `&group_children=${childrenAges.length}` + childrenAges.map(age => `&age=${age}`).join("") : "";
  const bookingDirectLink = activeCity ? `https://www.booking.com/searchresults.html?ss=${encodeURIComponent(activeCity.split(",")[0].trim())}${startDate ? `&checkin=${startDate}` : ""}${endDate ? `&checkout=${endDate}` : ""}&group_adults=${adults}${childrenQuery}&no_rooms=${normalizedHotelRooms}` : "#";

  const updateHotelRooms = (nextRooms) => {
    setHotelRooms(normalizeHotelRoomsCount(nextRooms, travelersCount));
  };

  useEffect(() => {
    setActiveCity(primaryCity);
  }, [primaryCity]);

  useEffect(() => {
    setHotelRooms((currentRooms) => normalizeHotelRoomsCount(currentRooms, travelersCount));
  }, [travelersCount]);

  useEffect(() => {
    if (!activeCity) return;
    setTriggered(false);
    setData([]);
    setProvider(null);
    setLoaded(false);
    if (isRussia) {
      doFetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCity]);

  useEffect(() => {
    if (lastPassengerSignatureRef.current === passengerSignature) return;
    lastPassengerSignatureRef.current = passengerSignature;
    if (!activeCity) return;
    if (triggered || isRussia) {
      doFetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCity, isRussia, passengerSignature, triggered]);

  useEffect(() => {
    if (!activeCity) return;
    if (triggered || isRussia) {
      doFetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotelCurrency, hotelLocale]);

  if (!city) return null;

  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  const roomsControlLabel = isRussia ? t.hotelUnitsLabel : t.hotelRoomsLabel;
  const ostrovokHint = formatRuProviderHint("ostrovok", accommodationPlan, lang);
  const sutochnoHint = formatRuProviderHint("sutochno", accommodationPlan, lang);
  const ratingOptions = [
    { id: 0, label: t.hotelAnyOption },
    { id: 10, label: "10" },
    { id: 9, label: "9+" },
    { id: 8, label: "8+" },
    { id: 7, label: "7+" },
  ];
  const bedroomsOptions = [
    { id: 0, label: t.hotelAnyOption },
    { id: 2, label: `${t.hotelFromOption} 2` },
    { id: 3, label: `${t.hotelFromOption} 3` },
    { id: 4, label: `${t.hotelFromOption} 4` },
    { id: 5, label: `${t.hotelFromOption} 5` },
    { id: 6, label: `${t.hotelFromOption} 6` },
  ];
  const roomOptions = Array.from({ length: roomLimit }, (_, index) => ({
    id: index + 1,
    label: String(index + 1),
  }));
  const ratingSummary = ratingOptions.find((option) => option.id === normalizedHotelRating)?.label || t.hotelAnyOption;
  const bedroomsSummary = bedroomsOptions.find((option) => option.id === normalizedHotelMinBedrooms)?.label || t.hotelAnyOption;
  const roomSummary = `${normalizedHotelRooms}`;

  return (
    <TravelSectionShell
      sectionKey={`hotels-${city}-${startDate || ""}-${endDate || ""}-${compact ? "compact" : "full"}`}
      title={t.hotelsTitle}
      icon={<HotelIcon />}
      defaultExpanded={!compact}
      summary={triggered
        ? `${data.length || 0} ${lang === "en" ? "options" : "вариантов"}`
        : t.hotelsSummary}
      actions={
        loaded && data.length > 0 && provider !== "ru_widgets" && !isRussia ? (
          <a href={bookingDirectLink} target="_blank" rel="noopener noreferrer" className="booking-corner-link" title={t.goToBooking}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </a>
        ) : null
      }
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      <div className="hotels-filter-wrap">
        {isRussia && (
          <div className="ru-hotels-settings-card">
            <div className="ru-hotels-settings-header">{t.hotelFiltersTitle}</div>
            <div className="ru-hotels-settings-grid">
              {showRoomsControl && (
                <div className="ru-hotels-settings-group">
                  <TripSettingsDropdown
                    label={roomsControlLabel}
                    value={normalizedHotelRooms}
                    onChange={(value) => updateHotelRooms(value)}
                    options={roomOptions}
                    summary={roomSummary}
                  />
                </div>
              )}
              <div className="ru-hotels-settings-group">
                <TripSettingsDropdown
                  label={t.hotelRatingLabel}
                  value={normalizedHotelRating}
                  onChange={(value) => setHotelRating(value)}
                  options={ratingOptions}
                  summary={ratingSummary}
                />
              </div>
              <div className="ru-hotels-settings-group">
                <TripSettingsDropdown
                  label={t.hotelBedroomsLabel}
                  value={normalizedHotelMinBedrooms}
                  onChange={(value) => setHotelMinBedrooms(value)}
                  options={bedroomsOptions}
                  summary={bedroomsSummary}
                />
              </div>
              <div className="ru-hotels-settings-group ru-hotels-settings-group-price">
                <span className="ru-hotels-settings-label">{t.hotelPriceLabel}</span>
                <div className="ru-hotels-price-row">
                  <input
                    className="ru-hotels-price-input"
                    inputMode="numeric"
                    placeholder={t.hotelPriceFromPlaceholder}
                    value={hotelPriceMin}
                    onChange={(event) => setHotelPriceMin(normalizeHotelPriceValue(event.target.value))}
                  />
                  <input
                    className="ru-hotels-price-input"
                    inputMode="numeric"
                    placeholder={t.hotelPriceToPlaceholder}
                    value={hotelPriceMax}
                    onChange={(event) => setHotelPriceMax(normalizeHotelPriceValue(event.target.value))}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
        <div className="hotels-buttons-row">
          {!triggered && (
            <button className="flights-search-btn hotels-action-btn" onClick={doFetch}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                <polyline points="9 22 9 12 15 12 15 22" />
              </svg>
              {t.showHotels}
            </button>
          )}
          {!isRussia && !triggered && (
            <a href={bookingDirectLink} target="_blank" rel="noopener noreferrer" className="booking-secondary-btn hotels-action-btn" title={t.searchDirectlyBooking}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
              {t.goToBooking}
            </a>
          )}
        </div>
      </div>
      {loading ? (
        <div className="loading-spinner-wrap">
          <div className="loading-spinner" />
          <span className="loading-text">{t.searchingHotels}</span>
        </div>
      ) : provider === "ru_widgets" ? (
        <div className="ru-widgets-container">
          <div className="ru-widgets-grid">
            <a href={links.ostrovok} target="_blank" rel="noopener noreferrer" className="ru-widget-card">
              <h4 className="ru-widget-title">Ostrovok.ru</h4>
              <p className="ru-widget-description">
                <span className="ru-widget-copy-full">
                  {lang === "en"
                    ? "Hotels and apartments across Russia"
                    : "Более миллиона отелей и апартаментов по всей России"}
                </span>
                <span className="ru-widget-copy-mobile">
                  {lang === "en" ? "Hotels in Russia" : "Отели и апартаменты"}
                </span>
              </p>
              <p className="ru-widget-plan">{ostrovokHint}</p>
              <div className="ru-widget-cta ru-widget-cta-subtle">
                <span className="ru-widget-cta-full">{lang === "en" ? "Search Ostrovok" : "Поиск на Ostrovok"}</span>
                <span className="ru-widget-cta-mobile">{lang === "en" ? "Open" : "Открыть"}</span>
              </div>
            </a>
            <a href={links.sutochno} target="_blank" rel="noopener noreferrer" className="ru-widget-card">
              <h4 className="ru-widget-title">Суточно.ру</h4>
              <p className="ru-widget-description">
                <span className="ru-widget-copy-full">
                  {lang === "en"
                    ? "Private apartments and daily rentals"
                    : "Лучший сервис для аренды частного жилья и квартир"}
                </span>
                <span className="ru-widget-copy-mobile">
                  {lang === "en" ? "Daily rentals" : "Квартиры посуточно"}
                </span>
              </p>
              <p className="ru-widget-plan">{sutochnoHint}</p>
              <div className="ru-widget-cta ru-widget-cta-subtle">
                <span className="ru-widget-cta-full">{lang === "en" ? "Search Sutochno" : "Поиск на Суточно"}</span>
                <span className="ru-widget-cta-mobile">{lang === "en" ? "Open" : "Открыть"}</span>
              </div>
            </a>
          </div>
        </div>
      ) : loaded && data.length === 0 ? (
        <div style={{ textAlign: "center", color: "#9ca3af", padding: "1rem 0" }}>
          {t.noHotelsFound}
        </div>
      ) : (
        <div className="hotels-grid">
          {data.map((h, i) => (
            <a key={i} href={h.link} target="_blank" rel="noopener noreferrer" className="hotel-card">
              {h.image ? (
                <img src={h.image} alt={h.name} className="hotel-img" loading="lazy" />
              ) : (
                <div className="hotel-img-placeholder" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><HotelIcon style={{ width: '32px', height: '32px', color: 'var(--text-secondary)' }} /></div>
              )}
              <div className="hotel-body">
                <div className="hotel-name">{h.name}</div>
                <div className="hotel-meta">
                  {h.stars > 0 && <span className="hotel-stars">{"★".repeat(h.stars)}</span>}
                  {h.rating && (
                    <span className="hotel-rating-badge">
                      {h.rating}
                      {h.review_word && <span className="hotel-review-word"> · {h.review_word}</span>}
                    </span>
                  )}
                </div>
                {h.price_per_night && (() => {
                  const mainCurrency = lang === "en" ? "USD" : h.currency;
                  const mainValue = lang === "en"
                    ? (h.currency === "USD" ? h.price_per_night : h.price_usd || h.price_per_night)
                    : h.price_per_night;
                  return (
                    <div className="hotel-price">
                      <span className="hotel-price-main">
                        {formatHotelCurrencyPrice(mainCurrency, mainValue, lang)} / {t.perNight}
                      </span>
                      {lang !== "en" && h.price_rub && h.currency !== "RUB" && (
                        <span className="hotel-price-rub">~{h.price_rub.toLocaleString("ru-RU")} ₽</span>
                      )}
                    </div>
                  );
                })()}
              </div>
            </a>
          ))}
        </div>
      )}
    </TravelSectionShell>
  );
});

const EsimSection = React.memo(({ city, lang, compact = false }) => {
  const citiesList = city ? (city.includes(" + ") ? city.split(" + ").map(c => c.trim()) : [city]) : [];
  const [activeCity, setActiveCity] = useState(citiesList[0] || "");

  const [data, setData] = useState(null);
  const [browseLink, setBrowseLink] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!activeCity) return;
    setData(null);
    setBrowseLink("");
    setLoading(true);
    setLoaded(false);
    const params = new URLSearchParams({ city: activeCity, lang });
    fetch(`${API_URL}/esim/search?${params}`)
      .then(r => r.json())
      .then(d => {
        setData(d.esim || null);
        if (d.browse_link) setBrowseLink(d.browse_link);
      })
      .catch(() => setData(null))
      .finally(() => { setLoading(false); setLoaded(true); });
  }, [activeCity, lang]);

  if (loaded && !data && !browseLink) return null;
  if (!loaded && !loading) return null;

  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;

  return (
    <TravelSectionShell
      sectionKey={`esim-${city}-${lang}-${compact ? "compact" : "full"}`}
      title={t.esimTitle}
      icon={<SmartphoneIcon />}
      defaultExpanded={!compact}
      summary={lang === "en" ? "Connectivity" : "Связь в поездке"}
    >
      {citiesList.length > 1 && (
        <div className="city-tabs">
          {citiesList.map((c, i) => (
            <button
              key={i}
              className={`city-tab ${activeCity === c ? "active" : ""}`}
              onClick={() => setActiveCity(c)}
            >
              {c.split(",")[0]}
            </button>
          ))}
        </div>
      )}
      {loading ? (
        <div className="skeleton-grid">
          <div className="skeleton-card short" />
        </div>
      ) : (
        <div className="esim-content">
          {data ? (
            <div className="esim-card">
              <div className="esim-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><SmartphoneIcon style={{ width: '32px', height: '32px' }} /></div>
              <div className="esim-details">
                <div className="esim-country">{data.country}</div>
                <div className="esim-provider">
                  <span className="esim-provider-badge">Airalo</span>
                </div>
                <div className="esim-description">
                  {t.esimDesc}
                </div>
              </div>
              <a href={data.link} target="_blank" rel="noopener noreferrer" className="esim-cta-btn">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="5" y="2" width="14" height="20" rx="2" ry="2" /><line x1="12" y1="18" x2="12" y2="18" />
                </svg>
                {t.chooseEsim}
              </a>
            </div>
          ) : (
            browseLink && (
              <div className="esim-card esim-generic">
                <div className="esim-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><GlobeIcon style={{ width: '32px', height: '32px' }} /></div>
                <div className="esim-details">
                  <div className="esim-description">
                    {t.esimDescBrowse}
                  </div>
                </div>
                <a href={browseLink} target="_blank" rel="noopener noreferrer" className="esim-cta-btn">
                  {t.browseEsim}
                </a>
              </div>
            )
          )}
        </div>
      )}
    </TravelSectionShell>
  );
});

// === Itinerary Section ===
const ItinerarySection = React.memo(({ checklist, lang, slug, isOwner, realOwnerId, currentUserId, hiddenSections, onToggleVisibility, requestConfirm, highlightedEventIds = [] }) => {
  const [events, setEvents] = useState(checklist?.events || []);
  const [addingDay, setAddingDay] = useState(null);
  const [newEvent, setNewEvent] = useState({ time: "", title: "", description: "", address: "" });
  const [loading, setLoading] = useState(false);
  const [showItinerary, setShowItinerary] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [editData, setEditData] = useState({ time: "", title: "", description: "", address: "" });
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  const token = localStorage.getItem("token");

  // Sync state if checklist changes externally 
  useEffect(() => {
    if (checklist?.events) setEvents(checklist.events);
  }, [checklist]);

  useEffect(() => {
    if ((highlightedEventIds || []).length > 0) {
      setShowItinerary(true);
    }
  }, [highlightedEventIds]);

  if (!checklist || !checklist.start_date || !checklist.end_date) return null;

  // Generate days timeline
  const startDt = new Date(checklist.start_date);
  const endDt = new Date(checklist.end_date);
  const days = [];
  let curr = new Date(startDt);
  while (curr <= endDt) {
    days.push(new Date(curr));
    curr.setDate(curr.getDate() + 1);
  }

  const handleAddSubmit = async (dateStr) => {
    if (!newEvent.title) return alert("Введите название события");
    setLoading(true);
    try {
      const resp = await fetch(`${API_URL}/checklists/${slug}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          event_date: dateStr,
          time: newEvent.time || null,
          title: newEvent.title,
          description: newEvent.description || null,
          address: newEvent.address || null
        })
      });
      if (resp.ok) {
        const ev = await resp.json();
        setEvents([...events, ev]);
        setAddingDay(null);
        setNewEvent({ time: "", title: "", description: "", address: "" });
      } else {
        alert("Ошибка при сохранении события");
      }
    } catch (e) {
      console.error(e);
      alert("Сбой сети");
    }
    setLoading(false);
  };

  const handleEditSubmit = async (eventId) => {
    if (!editData.title) return alert("Введите название события");
    const originalEvent = events.find(event => event.id === eventId);
    setLoading(true);
    try {
      const resp = await fetch(`${API_URL}/events/${eventId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          time: editData.time || null,
          title: editData.title,
          description: editData.description || null,
          address: editData.address || null
        })
      });
      if (resp.ok) {
        const updated = await resp.json();
        let nextEvents = events.map(ev => ev.id === eventId ? updated : ev);
        const shouldCascadeTimes = originalEvent
          && originalEvent.event_date === updated.event_date
          && originalEvent.time !== updated.time
          && updated.time;
        const cascadedUpdates = shouldCascadeTimes ? buildCascadedEventTimeUpdates(nextEvents, updated) : [];
        if (cascadedUpdates.length > 0) {
          const persistedCascade = [];
          for (const cascadedEvent of cascadedUpdates) {
            const cascadeResp = await fetch(`${API_URL}/events/${cascadedEvent.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
              body: JSON.stringify({ time: cascadedEvent.time })
            });
            if (cascadeResp.ok) {
              persistedCascade.push(await cascadeResp.json());
            }
          }
          const cascadeMap = new Map(persistedCascade.map(event => [event.id, event]));
          nextEvents = nextEvents.map(event => cascadeMap.get(event.id) || event);
        }
        setEvents(nextEvents);
        setEditingEvent(null);
      } else {
        alert("Ошибка при сохранении изменений");
      }
    } catch (e) {
      console.error(e);
      alert("Сбой сети");
    }
    setLoading(false);
  };

  const handleRemoveEvent = async (eventId) => {
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete event" : "Удалить событие",
      message: lang === "en" ? "This action cannot be undone." : "Это действие нельзя отменить.",
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) return;
    try {
      const resp = await fetch(`${API_URL}/events/${eventId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (resp.ok) {
        setEvents(events.filter(ev => ev.id !== eventId));
      } else {
        alert("Ошибка при удалении");
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className={`forecast-section ${!showItinerary ? 'collapsed' : ''}`}>
      <div className="forecast-header">
        <div className="forecast-header-left" onClick={() => setShowItinerary(!showItinerary)}>
          <h3><span style={{ display: 'flex', alignItems: 'center' }}><CalendarIcon /> {t.itineraryTitle || "План поездки"}</span></h3>
        </div>
        <div className="forecast-header-actions">
          {realOwnerId === currentUserId && (
            <span
              className={`section-visibility-toggle ${hiddenSections?.includes('itinerary') ? 'hidden' : 'visible'}`}
              onClick={(e) => { e.stopPropagation(); onToggleVisibility('itinerary'); }}
              title={hiddenSections?.includes('itinerary') ? 'План скрыт от других' : 'План виден всем'}
            >
              {hiddenSections?.includes('itinerary') ? <LockIcon style={{ marginRight: 0 }} /> : <UnlockIcon style={{ marginRight: 0 }} />}
            </span>
          )}
          <button className="collapse-toggle" onClick={() => setShowItinerary(!showItinerary)}>
            <span className={`chevron ${showItinerary ? 'up' : ''}`}>▾</span>
          </button>
        </div>
      </div>

      {showItinerary && (
        <div className="forecast-content itinerary-section">
          <div className="itinerary-timeline">
            {days.map((d, index) => {
              const dStr = d.toISOString().split("T")[0];
              const hasEvents = events.filter(e => e.event_date === dStr).sort(compareItineraryEvents);
              const isAdding = addingDay === dStr;

              return (
                <div key={dStr} className="itinerary-day-block">
                  <div className="itinerary-day-header">
                    <strong>{t.dayRoute} {index + 1}</strong>
                    <span className="itinerary-day-date">
                      • {d.toLocaleDateString(lang === "en" ? "en-US" : "ru-RU", { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                    {isOwner && hasEvents.length > 0 && (
                      <button
                        className="itinerary-clear-day-btn"
                        onClick={async () => {
                          const confirmed = await requestConfirm({
                            title: lang === "en" ? "Clear day" : "Очистить день",
                            message: lang === "en" ? `Delete all ${hasEvents.length} events for this day?` : `Удалить все ${hasEvents.length} событий за этот день?`,
                            confirmLabel: lang === "en" ? "Delete" : "Удалить",
                            cancelLabel: lang === "en" ? "Cancel" : "Отмена",
                            tone: "danger",
                          });
                          if (!confirmed) return;
                          for (const ev of hasEvents) {
                            try {
                              await fetch(`${API_URL}/events/${ev.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
                            } catch {}
                          }
                          setEvents(prev => prev.filter(e => e.event_date !== dStr));
                        }}
                        title={lang === "en" ? "Clear this day" : "Очистить день"}
                      >
                        {lang === "en" ? "Clear day" : "Очистить"}
                      </button>
                    )}
                  </div>

                  <div className="itinerary-events-list">
                    {hasEvents.length === 0 && !isAdding && (
                      <div className="itinerary-empty">{t.noEvents}</div>
                    )}
                    {hasEvents.map(ev => (
                      <div key={ev.id} className={`itinerary-event-card ${highlightedEventIds.includes(ev.id) ? 'itinerary-event-card-highlighted' : ''}`}>
                        {editingEvent === ev.id ? (
                          /* === Edit Mode === */
                          <div className="itinerary-form" style={{ flex: 1 }}>
                            <div className="itinerary-form-row">
                              <input type="time" value={editData.time || ""} onChange={e => setEditData({ ...editData, time: e.target.value })} />
                              <input type="text" value={editData.title} onChange={e => setEditData({ ...editData, title: e.target.value })} placeholder={t.eventTitlePlaceholder} autoFocus />
                            </div>
                            <input type="text" className="full-w" value={editData.description || ""} onChange={e => setEditData({ ...editData, description: e.target.value })} placeholder={t.eventDescPlaceholder} />
                            <input type="text" className="full-w" value={editData.address || ""} onChange={e => setEditData({ ...editData, address: e.target.value })} placeholder={lang === "ru" ? "📍 Адрес" : "📍 Address"} />
                            <div className="itinerary-form-actions">
                              <button className="action-btn primary" onClick={() => handleEditSubmit(ev.id)} disabled={loading}>{t.saveEventBtn}</button>
                              <button className="action-btn" onClick={() => setEditingEvent(null)}>{t.cancel}</button>
                            </div>
                          </div>
                        ) : (
                          /* === View Mode === */
                          <>
                            {ev.time && <div className="itinerary-event-time">{ev.time}</div>}
                            <div className="itinerary-event-content">
                              <div className="itinerary-event-title">{ev.title}</div>
                              {highlightedEventIds.includes(ev.id) && (
                                <div className="itinerary-event-badge">{lang === "en" ? "Added by AI" : "Добавлено AI"}</div>
                              )}
                              {ev.description && <div className="itinerary-event-desc">{ev.description}</div>}
                              {ev.address && (
                                <div className="itinerary-event-address">
                                  <a
                                    className="address-link"
                                    href={buildMapsPlaceUrl({
                                      lang,
                                      query: ev.address || ev.title,
                                      lat: ev.lat,
                                      lng: ev.lng,
                                    })}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={e => e.stopPropagation()}
                                  >
                                    📍 {ev.address}
                                  </a>
                                </div>
                              )}
                            </div>
                            {isOwner && (
                              <div className="evt-actions">
                                <button className="edit-evt-btn" onClick={() => { setEditingEvent(ev.id); setEditData({ time: ev.time || "", title: ev.title, description: ev.description || "", address: ev.address || "" }); }} title="Редактировать">✎</button>
                                <button className="del-evt-btn" onClick={() => handleRemoveEvent(ev.id)} title="Удалить">×</button>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    ))}

                    {/* Add new event slot */}
                    {isOwner && (
                      <div className="itinerary-add-slot">
                        {!isAdding ? (
                          <button className="add-evt-btn" onClick={() => setAddingDay(dStr)}>
                            {t.addEvent}
                          </button>
                        ) : (
                          <div className="itinerary-form">
                            <div className="itinerary-form-row">
                              <input
                                type="time"
                                value={newEvent.time}
                                onChange={e => setNewEvent({ ...newEvent, time: e.target.value })}
                                title={t.eventTimePlaceholder}
                              />
                              <input
                                type="text"
                                value={newEvent.title}
                                onChange={e => setNewEvent({ ...newEvent, title: e.target.value })}
                                placeholder={t.eventTitlePlaceholder}
                                autoFocus
                              />
                            </div>
                            <input
                              type="text"
                              className="full-w"
                              value={newEvent.description}
                              onChange={e => setNewEvent({ ...newEvent, description: e.target.value })}
                              placeholder={t.eventDescPlaceholder}
                            />
                            <input
                              type="text"
                              className="full-w"
                              value={newEvent.address}
                              onChange={e => setNewEvent({ ...newEvent, address: e.target.value })}
                              placeholder={lang === "ru" ? "📍 Адрес (необязательно)" : "📍 Address (optional)"}
                            />
                            <div className="itinerary-form-actions">
                              <button className="action-btn primary" onClick={() => handleAddSubmit(dStr)} disabled={loading}>
                                {t.saveEventBtn}
                              </button>
                              <button className="action-btn" onClick={() => { setAddingDay(null); setNewEvent({ time: "", title: "", description: "", address: "" }); }}>
                                {t.cancel}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {isOwner && events.length > 0 && (
            <button
              className="itinerary-clear-all-btn"
              onClick={async () => {
                const confirmed = await requestConfirm({
                  title: lang === "en" ? "Clear entire plan" : "Очистить весь план",
                  message: lang === "en" ? `Delete all ${events.length} events? This cannot be undone.` : `Удалить все ${events.length} событий? Это нельзя отменить.`,
                  confirmLabel: lang === "en" ? "Delete all" : "Удалить всё",
                  cancelLabel: lang === "en" ? "Cancel" : "Отмена",
                  tone: "danger",
                });
                if (!confirmed) return;
                for (const ev of events) {
                  try {
                    await fetch(`${API_URL}/events/${ev.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
                  } catch {}
                }
                setEvents([]);
              }}
            >
              {lang === "en" ? "Clear entire plan" : "Очистить весь план"}
            </button>
          )}
        </div>
      )}
    </div>
  );
});

const getTripMapStyleUrl = (theme = "dark") => (
  theme === "light"
    ? "https://tiles.openfreemap.org/styles/positron"
    : "https://tiles.openfreemap.org/styles/liberty"
);

const getTripMapFallbackStyle = (theme = "dark") => ({
  version: 8,
  name: "Luggify fallback map",
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap",
    },
  },
  layers: [
    {
      id: "luggify-map-bg",
      type: "background",
      paint: {
        "background-color": theme === "light" ? "#f7f1e8" : "#181511",
      },
    },
    {
      id: "luggify-osm-raster",
      type: "raster",
      source: "osm",
      paint: {
        "raster-opacity": theme === "light" ? 0.42 : 0.28,
        "raster-saturation": -0.45,
      },
    },
  ],
});

const getTripMapColors = () => {
  if (typeof window === "undefined") {
    return { accent: "#c87442", accentSoft: "rgba(200, 116, 66, 0.24)", text: "#f4ede4" };
  }
  const styles = window.getComputedStyle(document.documentElement);
  return {
    accent: styles.getPropertyValue("--orange").trim() || "#c87442",
    accentSoft: styles.getPropertyValue("--orange-glow-strong").trim() || "rgba(200, 116, 66, 0.24)",
    text: styles.getPropertyValue("--text-primary").trim() || "#f4ede4",
  };
};

const escapeMapPopupText = (value = "") => (
  String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
);

const getTripMapPlaceTypeLabel = (event = {}, lang = "ru") => {
  const normalized = String(event.event_type || "").trim().toLowerCase();
  const labels = {
    attraction: { ru: "Достопримечательность", en: "Attraction" },
    restaurant: { ru: "Еда", en: "Food" },
    food: { ru: "Еда", en: "Food" },
    museum: { ru: "Музей", en: "Museum" },
    park: { ru: "Парк", en: "Park" },
    hotel: { ru: "Жильё", en: "Stay" },
    transfer: { ru: "Переезд", en: "Transfer" },
    activity: { ru: "Активность", en: "Activity" },
  };
  if (labels[normalized]) return labels[normalized][lang] || labels[normalized].ru;
  if (/музе|museum/i.test(event.title || "")) return lang === "en" ? "Museum" : "Музей";
  if (/парк|park/i.test(event.title || "")) return lang === "en" ? "Park" : "Парк";
  if (/обед|ужин|кафе|ресторан|lunch|dinner|cafe|restaurant/i.test(event.title || "")) return lang === "en" ? "Food" : "Еда";
  return lang === "en" ? "Place" : "Место";
};

const getTripMapPlaceKind = (event = {}) => {
  const normalized = String(event.event_type || "").trim().toLowerCase();
  if (["food", "restaurant", "cafe", "bar"].includes(normalized)) return "food";
  if (["hotel", "stay", "accommodation"].includes(normalized)) return "stay";
  if (/обед|ужин|кафе|ресторан|lunch|dinner|cafe|restaurant/i.test(event.title || "")) return "food";
  return "place";
};

const getTripMapPlaceImage = (event = {}) => {
  const meta = event?.meta && typeof event.meta === "object" ? event.meta : {};
  return (
    meta.image
    || meta.image_url
    || meta.photo
    || meta.photo_url
    || meta.thumbnail
    || meta.attraction_image
    || ""
  );
};

const buildTripMapPopupHtml = (event, index, lang = "ru", compact = false) => {
  const title = escapeMapPopupText(event.title);
  const address = escapeMapPopupText(event.address || "");
  const description = escapeMapPopupText(event.description || "");
  const typeLabel = escapeMapPopupText(getTripMapPlaceTypeLabel(event, lang));
  const dateLabel = event.event_date
    ? escapeMapPopupText(new Date(`${event.event_date}T00:00:00`).toLocaleDateString(formatChecklistLocale(lang), { day: "numeric", month: "short" }))
    : "";
  const routeUrl = buildMapsPlaceUrl({
    lang,
    query: event.address || event.title,
    lat: event.lat,
    lng: event.lng,
  });
  const safeRouteUrl = escapeMapPopupText(routeUrl);
  if (compact) {
    return `
      <div class="trip-map-popup-card trip-map-popup-card-compact">
        <strong>${title}</strong>
        ${typeLabel ? `<span>${typeLabel}</span>` : ""}
      </div>
    `;
  }
  return `
    <div class="trip-map-popup-card">
      <div class="trip-map-popup-top">
        <span class="trip-map-popup-index">${index + 1}</span>
        <span class="trip-map-popup-type">${typeLabel}</span>
      </div>
      <strong>${title}</strong>
      ${description ? `<p>${description}</p>` : ""}
      <div class="trip-map-popup-meta">
        ${dateLabel ? `<span>${dateLabel}</span>` : ""}
        ${event.duration_minutes ? `<span>${event.duration_minutes} ${lang === "en" ? "min" : "мин"}</span>` : ""}
      </div>
      ${address ? `<a href="${safeRouteUrl}" target="_blank" rel="noopener noreferrer" class="trip-map-popup-address">📍 ${address}</a>` : ""}
    </div>
  `;
};

const TripMapSection = React.memo(({ checklist, lang, compact = false, highlightedEventIds = [], theme = "dark" }) => {
  const mapRef = useRef(null);
  const maplibreRef = useRef(null);
  const containerRef = useRef(null);
  const markersRef = useRef([]);
  const popupRef = useRef(null);
  const hoverPopupRef = useRef(null);
  const fallbackTimerRef = useRef(null);
  const [expanded, setExpanded] = useState(!compact);
  const [mapReady, setMapReady] = useState(false);
  const [mapLoading, setMapLoading] = useState(false);
  const [selectedDayKey, setSelectedDayKey] = useState("all");
  const [activeMapPlace, setActiveMapPlace] = useState(null);
  const eventsWithCoords = useMemo(() => (
    (checklist?.events || [])
      .map((event) => ({ event, coords: getEventCoordinates(event) }))
      .filter((item) => item.coords)
      .sort((a, b) => compareItineraryEvents(a.event, b.event))
  ), [checklist?.events]);
  const dayOptions = useMemo(() => {
    const uniqueDates = Array.from(new Set(eventsWithCoords.map(({ event }) => event.event_date).filter(Boolean)));
    return uniqueDates.map((dateKey, index) => ({
      key: dateKey,
      label: lang === "en" ? `Day ${index + 1}` : `День ${index + 1}`,
      dateLabel: new Date(`${dateKey}T00:00:00`).toLocaleDateString(
        formatChecklistLocale(lang),
        { day: "numeric", month: "short" }
      ),
    }));
  }, [eventsWithCoords, lang]);
  const activeEvents = useMemo(() => (
    selectedDayKey === "all"
      ? eventsWithCoords
      : eventsWithCoords.filter(({ event }) => event.event_date === selectedDayKey)
  ), [eventsWithCoords, selectedDayKey]);
  const selectedMapOption = selectedDayKey === "all"
    ? "all"
    : dayOptions.find((option) => option.key === selectedDayKey)?.key || "all";
  useEffect(() => {
    if (selectedDayKey === "all") return;
    if (!dayOptions.some((option) => option.key === selectedDayKey)) {
      setSelectedDayKey("all");
    }
  }, [dayOptions, selectedDayKey]);

  useEffect(() => {
    if (!activeMapPlace) return;
    if (!activeEvents.some(({ event }) => event.id === activeMapPlace.event.id)) {
      setActiveMapPlace(null);
    }
  }, [activeEvents, activeMapPlace]);

  useEffect(() => {
    if (!expanded || !containerRef.current || mapRef.current) return;
    setMapReady(false);
    setMapLoading(true);
    let cancelled = false;
    let mapBaseReady = false;

    const initializeMap = async () => {
      const { default: maplibregl } = await import("maplibre-gl");
      if (cancelled || !containerRef.current || mapRef.current) return;
      maplibreRef.current = maplibregl;
      const createMap = (style) => new maplibregl.Map({
          container: containerRef.current,
          style,
          center: [37.618423, 55.751244],
          zoom: 10,
          attributionControl: false,
        });
      const map = createMap(getTripMapStyleUrl(theme));
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
      map.scrollZoom.disable();
      mapRef.current = map;

      const finishMapSetup = () => {
        if (cancelled) return;
        if (fallbackTimerRef.current) {
          window.clearTimeout(fallbackTimerRef.current);
          fallbackTimerRef.current = null;
        }
        mapBaseReady = true;
        setMapReady(true);
        setMapLoading(false);
        window.setTimeout(() => map.resize(), 80);
      };

      map.once("load", finishMapSetup);
      map.once("error", () => {
        if (mapBaseReady || cancelled) return;
        map.setStyle(getTripMapFallbackStyle(theme));
        map.once("style.load", finishMapSetup);
      });
      fallbackTimerRef.current = window.setTimeout(() => {
        if (cancelled || mapBaseReady) return;
        map.setStyle(getTripMapFallbackStyle(theme));
        map.once("style.load", finishMapSetup);
      }, 2800);
    };

    initializeMap();
    return () => {
      cancelled = true;
      if (fallbackTimerRef.current) {
        window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
      }
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
      hoverPopupRef.current?.remove();
      hoverPopupRef.current = null;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      maplibreRef.current = null;
      setMapReady(false);
      setMapLoading(false);
    };
  }, [expanded, theme]);

  useEffect(() => {
    if (!expanded || !mapRef.current || !mapReady) return;
    const map = mapRef.current;
    const maplibregl = maplibreRef.current;
    if (!maplibregl) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];
    hoverPopupRef.current?.remove();
    hoverPopupRef.current = null;

    if (activeEvents.length === 0) return;

    const colors = getTripMapColors();
    activeEvents.forEach(({ event, coords }, index) => {
      const markerEl = document.createElement("button");
      markerEl.type = "button";
      markerEl.className = `trip-map-marker ${highlightedEventIds.includes(event.id) ? "highlighted" : ""}`;
      markerEl.style.setProperty("--marker-color", highlightedEventIds.includes(event.id) ? colors.text : colors.accent);
      markerEl.innerHTML = `<span>${index + 1}</span>`;
      markerEl.addEventListener("mouseenter", () => {
        if (popupRef.current) return;
        hoverPopupRef.current?.remove();
        hoverPopupRef.current = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 18,
          className: "trip-map-popup trip-map-hover-popup",
        })
          .setLngLat([coords[1], coords[0]])
          .setHTML(buildTripMapPopupHtml(event, index, lang, true))
          .addTo(map);
      });
      markerEl.addEventListener("mouseleave", () => {
        hoverPopupRef.current?.remove();
        hoverPopupRef.current = null;
      });
      markerEl.addEventListener("click", () => {
        hoverPopupRef.current?.remove();
        hoverPopupRef.current = null;
        setActiveMapPlace({ event, index });
        map.easeTo({
          center: [coords[1], coords[0]],
          zoom: Math.max(map.getZoom(), 14),
          offset: compact ? [0, -80] : [-160, 0],
          duration: 420,
        });
      });
      const marker = new maplibregl.Marker({ element: markerEl, anchor: "center" })
        .setLngLat([coords[1], coords[0]])
        .addTo(map);
      markersRef.current.push(marker);
    });

    if (activeEvents.length === 1) {
      const [lat, lng] = activeEvents[0].coords;
      map.easeTo({ center: [lng, lat], zoom: Math.max(map.getZoom(), 13), duration: 520 });
    } else {
      const bounds = activeEvents.reduce((nextBounds, item) => (
        nextBounds.extend([item.coords[1], item.coords[0]])
      ), new maplibregl.LngLatBounds(
        [activeEvents[0].coords[1], activeEvents[0].coords[0]],
        [activeEvents[0].coords[1], activeEvents[0].coords[0]]
      ));
      map.fitBounds(bounds, { padding: compact ? 42 : 64, maxZoom: 14, duration: 620 });
    }
    window.setTimeout(() => map.resize(), 80);
  }, [expanded, mapReady, activeEvents, highlightedEventIds, compact, lang]);

  if (eventsWithCoords.length === 0) return null;

  return (
    <div className={`forecast-section trip-map-section ${!expanded ? "collapsed" : ""}`}>
      <div className="forecast-header">
        <div className="forecast-header-left" onClick={() => setExpanded(!expanded)}>
          <h3><span style={{ display: "flex", alignItems: "center" }}><MapIcon /> {lang === "en" ? "Route map" : "Карта маршрута"}</span></h3>
        </div>
        <div className="forecast-header-actions">
          <button className="collapse-toggle" onClick={() => setExpanded(!expanded)}>
            <span className={`chevron ${expanded ? "up" : ""}`}>▾</span>
          </button>
        </div>
      </div>
      {expanded && (
        <div className="trip-map-content">
          <div className="trip-map-shell">
            <div ref={containerRef} className="trip-map-canvas" />
            {mapLoading && (
              <div className="trip-map-loading">
                {lang === "en" ? "Loading map..." : "Загружаем карту..."}
              </div>
            )}
            <div className="trip-map-control">
              <select
                value={selectedMapOption}
                onChange={(event) => setSelectedDayKey(event.target.value)}
                aria-label={lang === "en" ? "Map day" : "День на карте"}
              >
                <option value="all">{lang === "en" ? "Whole trip" : "Вся поездка"}</option>
                {dayOptions.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label} · {option.dateLabel}
                  </option>
                ))}
              </select>
              <strong>{activeEvents.length}</strong>
            </div>
            {activeMapPlace && (
              <div className={`trip-map-place-card ${getTripMapPlaceKind(activeMapPlace.event) === "food" ? "food" : ""}`}>
                <button
                  type="button"
                  className="trip-map-place-close"
                  onClick={() => setActiveMapPlace(null)}
                  aria-label={lang === "en" ? "Close place card" : "Закрыть карточку места"}
                >
                  ×
                </button>
                {getTripMapPlaceKind(activeMapPlace.event) !== "food" && (
                  <div className="trip-map-place-media">
                    {getTripMapPlaceImage(activeMapPlace.event) ? (
                      <img src={getTripMapPlaceImage(activeMapPlace.event)} alt={activeMapPlace.event.title} loading="lazy" />
                    ) : (
                      <div className="trip-map-place-media-fallback">
                        <MapIcon />
                      </div>
                    )}
                  </div>
                )}
                <div className="trip-map-place-body">
                  <div className="trip-map-place-top">
                    <span className="trip-map-place-index">{activeMapPlace.index + 1}</span>
                    <span className="trip-map-place-type">{getTripMapPlaceTypeLabel(activeMapPlace.event, lang)}</span>
                  </div>
                  <strong>{activeMapPlace.event.title}</strong>
                  <p>
                    {activeMapPlace.event.description
                      || (getTripMapPlaceKind(activeMapPlace.event) === "food"
                        ? (lang === "en" ? "A food stop in the route. Check the address and open it in maps when you are ready." : "Точка для еды по маршруту. Можно быстро открыть адрес в картах.")
                        : (lang === "en" ? "A route stop with saved coordinates and address." : "Точка маршрута с сохранёнными координатами и адресом."))}
                  </p>
                  {activeMapPlace.event.address && (
                    <a
                      href={buildMapsPlaceUrl({
                        lang,
                        query: activeMapPlace.event.address || activeMapPlace.event.title,
                        lat: activeMapPlace.event.lat,
                        lng: activeMapPlace.event.lng,
                      })}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="trip-map-place-address"
                    >
                      📍 {activeMapPlace.event.address}
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

const ExpensesSection = React.memo(({
  checklist,
  lang,
  slug,
  token,
  canEdit,
  realOwnerId,
  currentUserId,
  hiddenSections,
  onToggleVisibility,
  onChecklistUpdated,
  requestConfirm,
  isOffline,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [expenses, setExpenses] = useState(checklist?.expenses || []);
  const [summary, setSummary] = useState(checklist?.expense_summary || null);
  const [budgetAmount, setBudgetAmount] = useState(
    checklist?.expense_budget_amount != null ? String(checklist.expense_budget_amount) : ""
  );
  const [baseCurrency, setBaseCurrency] = useState(normalizeExpenseCurrency(checklist?.expense_base_currency || "RUB"));
  const localCurrency = getExpenseLocalCurrency(checklist);
  const [draft, setDraft] = useState({
    expense_date: checklist?.start_date || "",
    title: "",
    category: "other",
    amount: "",
    currency: localCurrency,
    note: "",
  });
  const [editingId, setEditingId] = useState(null);
  const [editingBudget, setEditingBudget] = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};
  const t = TRANSLATIONS[lang] || TRANSLATIONS.ru;
  const effectiveSummary = summary || {
    budget_amount: checklist?.expense_budget_amount,
    base_currency: checklist?.expense_base_currency || "RUB",
    total_spent: 0,
    remaining: checklist?.expense_budget_amount ?? null,
    by_category: {},
    expense_count: 0,
  };
  const effectiveCurrency = normalizeExpenseCurrency(effectiveSummary.base_currency || baseCurrency);
  const budgetCurrencyOptions = buildExpenseCurrencyOptions(
    effectiveCurrency,
    localCurrency,
    EXPENSE_BASE_CURRENCIES
  );
  const expenseCurrencyOptions = buildExpenseCurrencyOptions(
    localCurrency,
    effectiveCurrency,
    EXPENSE_BASE_CURRENCIES,
    draft.currency
  );
  const categoryOptions = EXPENSE_CATEGORIES.map((category) => ({
    id: category,
    label: getExpenseCategoryLabel(category, lang),
  }));

  useEffect(() => {
    setExpenses(checklist?.expenses || []);
    setSummary(checklist?.expense_summary || null);
    setBudgetAmount(checklist?.expense_budget_amount != null ? String(checklist.expense_budget_amount) : "");
    setBaseCurrency(normalizeExpenseCurrency(checklist?.expense_base_currency || "RUB"));
    setDraft((prev) => ({
      ...prev,
      expense_date: prev.expense_date || checklist?.start_date || "",
      currency: editingId ? prev.currency : getExpenseLocalCurrency(checklist),
    }));
  }, [checklist, editingId]);

  const applyExpenseResponse = (data) => {
    if (Array.isArray(data?.expenses)) setExpenses(data.expenses);
    if (data?.summary) setSummary(data.summary);
    if (data?.checklist && onChecklistUpdated) onChecklistUpdated(data.checklist);
  };

  const resetDraft = () => {
    setEditingId(null);
    setShowExpenseForm(false);
    setDraft({
      expense_date: checklist?.start_date || "",
      title: "",
      category: "other",
      amount: "",
      currency: getExpenseLocalCurrency(checklist) || normalizeExpenseCurrency(baseCurrency || "RUB"),
      note: "",
    });
  };

  const openNewExpenseForm = () => {
    setEditingId(null);
    setDraft((prev) => ({
      ...prev,
      expense_date: prev.expense_date || checklist?.start_date || "",
      category: prev.category || "other",
      currency: getExpenseLocalCurrency(checklist) || normalizeExpenseCurrency(baseCurrency || "RUB"),
    }));
    setShowExpenseForm(true);
  };

  const saveSettings = async () => {
    if (!slug || !token || busy) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/checklists/${slug}/expenses/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          budget_amount: budgetAmount === "" ? 0 : Number(budgetAmount),
          base_currency: normalizeExpenseCurrency(baseCurrency),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || (lang === "en" ? "Could not save budget." : "Не удалось сохранить бюджет."));
      applyExpenseResponse(data);
      setEditingBudget(false);
    } catch (error) {
      alert(error?.message || (lang === "en" ? "Could not save budget." : "Не удалось сохранить бюджет."));
    } finally {
      setBusy(false);
    }
  };

  const submitExpense = async () => {
    if (!slug || !token || busy || !draft.title.trim() || !draft.amount) return;
    setBusy(true);
    try {
      const payload = {
        expense_date: draft.expense_date || null,
        title: draft.title.trim(),
        category: draft.category,
        amount: Number(draft.amount),
        currency: normalizeExpenseCurrency(draft.currency),
        note: draft.note.trim() || null,
      };
      const res = await fetch(editingId ? `${API_URL}/expenses/${editingId}` : `${API_URL}/checklists/${slug}/expenses`, {
        method: editingId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || (lang === "en" ? "Could not save expense." : "Не удалось сохранить трату."));
      applyExpenseResponse(data);
      resetDraft();
    } catch (error) {
      alert(error?.message || (lang === "en" ? "Could not save expense." : "Не удалось сохранить трату."));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (expense) => {
    setEditingId(expense.id);
    setDraft({
      expense_date: expense.expense_date || "",
      title: expense.title || "",
      category: expense.category || "other",
      amount: String(expense.amount ?? ""),
      currency: normalizeExpenseCurrency(expense.currency || effectiveCurrency),
      note: expense.note || "",
    });
    setExpanded(true);
    setShowExpenseForm(true);
  };

  const deleteExpense = async (expense) => {
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete expense" : "Удалить трату",
      message: lang === "en" ? `Delete "${expense.title}"?` : `Удалить «${expense.title}»?`,
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/expenses/${expense.id}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || (lang === "en" ? "Could not delete expense." : "Не удалось удалить трату."));
      applyExpenseResponse(data);
      if (editingId === expense.id) resetDraft();
    } catch (error) {
      alert(error?.message || (lang === "en" ? "Could not delete expense." : "Не удалось удалить трату."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`forecast-section expenses-section ${!expanded ? "collapsed" : ""}`}>
      <div className="forecast-header">
        <div className="forecast-header-left" onClick={() => setExpanded(!expanded)}>
          <h3><span style={{ display: "flex", alignItems: "center" }}><WalletIcon /> {lang === "en" ? "Trip expenses" : "Траты поездки"}</span></h3>
        </div>
        <div className="forecast-header-actions">
          {realOwnerId === currentUserId && (
            <span
              className={`section-visibility-toggle ${hiddenSections?.includes("expenses") ? "hidden" : "visible"}`}
              onClick={(e) => { e.stopPropagation(); onToggleVisibility("expenses"); }}
              title={hiddenSections?.includes("expenses") ? (lang === "en" ? "Expenses hidden from others" : "Траты скрыты от других") : (lang === "en" ? "Expenses visible" : "Траты видны")}
            >
              {hiddenSections?.includes("expenses") ? <LockIcon style={{ marginRight: 0 }} /> : <UnlockIcon style={{ marginRight: 0 }} />}
            </span>
          )}
          <button className="collapse-toggle" onClick={() => setExpanded(!expanded)}>
            <span className={`chevron ${expanded ? "up" : ""}`}>▾</span>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="expenses-content">
          <div className="expenses-summary-grid">
            <div className={`expenses-summary-card expenses-budget-card ${editingBudget ? "editing" : ""}`}>
              <div className="expenses-summary-card-head">
                <span>{lang === "en" ? "Budget" : "Бюджет"}</span>
                {canEdit && !editingBudget && (
                  <button
                    type="button"
                    className="expenses-icon-btn"
                    onClick={() => {
                      setBudgetAmount(effectiveSummary.budget_amount != null ? String(effectiveSummary.budget_amount) : "");
                      setBaseCurrency(effectiveCurrency);
                      setEditingBudget(true);
                    }}
                    title={lang === "en" ? "Edit budget" : "Редактировать бюджет"}
                    disabled={busy || isOffline}
                  >
                    ✎
                  </button>
                )}
              </div>
              {editingBudget ? (
                <div className="expenses-budget-inline">
                  <input
                    className="expenses-input"
                    inputMode="decimal"
                    value={budgetAmount}
                    onChange={(e) => setBudgetAmount(normalizeExpenseAmountInput(e.target.value))}
                    placeholder={lang === "en" ? "Budget" : "Бюджет"}
                    disabled={busy || isOffline}
                  />
                  <TripSettingsDropdown
                    className="expenses-dropdown-field"
                    options={budgetCurrencyOptions}
                    value={baseCurrency}
                    onChange={setBaseCurrency}
                    placeholder={lang === "en" ? "Currency" : "Валюта"}
                    disabled={busy || isOffline}
                  />
                  <div className="expenses-inline-actions">
                    <button className="expenses-text-btn" onClick={() => setEditingBudget(false)} disabled={busy}>{t.cancel}</button>
                    <button className="expenses-text-btn primary" onClick={saveSettings} disabled={busy || isOffline}>
                      {lang === "en" ? "Save" : "Сохранить"}
                    </button>
                  </div>
                </div>
              ) : (
                <strong>{effectiveSummary.budget_amount != null ? formatMoney(effectiveSummary.budget_amount, effectiveCurrency, lang) : "—"}</strong>
              )}
            </div>
            <div className="expenses-summary-card">
              <span>{lang === "en" ? "Spent" : "Потрачено"}</span>
              <strong>{formatMoney(effectiveSummary.total_spent || 0, effectiveCurrency, lang)}</strong>
            </div>
            <div className={`expenses-summary-card ${(effectiveSummary.remaining ?? 0) < 0 ? "negative" : ""}`}>
              <span>{lang === "en" ? "Remaining" : "Осталось"}</span>
              <strong>{effectiveSummary.remaining != null ? formatMoney(effectiveSummary.remaining, effectiveCurrency, lang) : "—"}</strong>
            </div>
          </div>

          {canEdit && (
            <div className="expenses-editor">
              {!showExpenseForm ? (
                <div className="expenses-toolbar">
                  <button
                    className="action-btn primary"
                    onClick={openNewExpenseForm}
                    disabled={busy || isOffline}
                  >
                    {lang === "en" ? "Add expense" : "Добавить трату"}
                  </button>
                </div>
              ) : (
                <div className="expenses-form-shell">
                  <div className="expenses-form-title">
                    <strong>{editingId ? (lang === "en" ? "Edit expense" : "Редактировать трату") : (lang === "en" ? "New expense" : "Новая трата")}</strong>
                    <button className="expenses-icon-btn" onClick={resetDraft} disabled={busy} title={t.cancel}>×</button>
                  </div>
                  <div className="expenses-form">
                    <input className="expenses-input" type="date" value={draft.expense_date} onChange={(e) => setDraft({ ...draft, expense_date: e.target.value })} disabled={busy || isOffline} />
                    <input className="expenses-input expenses-title-input" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder={lang === "en" ? "Expense title" : "Название траты"} disabled={busy || isOffline} />
                    <TripSettingsDropdown
                      className="expenses-dropdown-field"
                      options={categoryOptions}
                      value={draft.category}
                      onChange={(category) => setDraft({ ...draft, category })}
                      placeholder={lang === "en" ? "Category" : "Категория"}
                      disabled={busy || isOffline}
                    />
                    <input className="expenses-input" inputMode="decimal" value={draft.amount} onChange={(e) => setDraft({ ...draft, amount: normalizeExpenseAmountInput(e.target.value) })} placeholder={lang === "en" ? "Amount" : "Сумма"} disabled={busy || isOffline} />
                    <TripSettingsDropdown
                      className="expenses-dropdown-field"
                      options={expenseCurrencyOptions}
                      value={draft.currency}
                      onChange={(currency) => setDraft({ ...draft, currency })}
                      placeholder={lang === "en" ? "Currency" : "Валюта"}
                      disabled={busy || isOffline}
                    />
                    <input className="expenses-input expenses-note-input" value={draft.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} placeholder={lang === "en" ? "Note" : "Заметка"} disabled={busy || isOffline} />
                    <div className="expenses-form-actions">
                      <button className="action-btn primary" onClick={submitExpense} disabled={busy || isOffline || !draft.title.trim() || !draft.amount}>
                        {editingId ? (lang === "en" ? "Save" : "Сохранить") : (lang === "en" ? "Add expense" : "Добавить трату")}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="expenses-category-strip">
            {Object.entries(effectiveSummary.by_category || {}).map(([category, amount]) => (
              <span key={category} className="expenses-category-pill">
                {getExpenseCategoryLabel(category, lang)} · {formatMoney(amount, effectiveCurrency, lang)}
              </span>
            ))}
          </div>

          <div className="expenses-list">
            {expenses.length === 0 ? (
              <div className="expenses-empty">{lang === "en" ? "No expenses yet." : "Пока нет трат."}</div>
            ) : expenses.map((expense) => (
              <div key={expense.id} className="expense-row">
                <div className="expense-row-main">
                  <strong>{expense.title}</strong>
                  <span>
                    {expense.expense_date ? new Date(expense.expense_date).toLocaleDateString(formatChecklistLocale(lang), { day: "numeric", month: "short" }) : ""}
                    {expense.expense_date ? " · " : ""}
                    {getExpenseCategoryLabel(expense.category, lang)}
                  </span>
                </div>
                <div className="expense-row-amount">
                  <strong>{formatMoney(expense.amount, expense.currency, lang)}</strong>
                  {expense.currency !== expense.base_currency && (
                    <span>~{formatMoney(expense.amount_base, expense.base_currency, lang)}</span>
                  )}
                </div>
                {canEdit && (
                  <div className="expense-row-actions">
                    <button className="edit-evt-btn" onClick={() => startEdit(expense)} title={lang === "en" ? "Edit" : "Редактировать"} disabled={busy || isOffline}>✎</button>
                    <button className="del-evt-btn" onClick={() => deleteExpense(expense)} title={lang === "en" ? "Delete" : "Удалить"} disabled={busy || isOffline}>×</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

const TripReviewsSection = React.memo(({ checklist, user, token, lang, canReview, onReviewSaved, requestConfirm }) => {
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [photos, setPhotos] = useState([]);
  const [saving, setSaving] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const photoInputRef = React.useRef(null);

  const tripEnded = Boolean(checklist?.end_date && checklist.end_date <= new Date().toISOString().slice(0, 10));
  const reviews = [...(checklist?.reviews || [])].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  const myReview = reviews.find((review) => review.user?.id === user?.id) || null;
  const averageRating = reviews.length
    ? (reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length).toFixed(1)
    : null;
  const getReviewPhotos = React.useCallback((review) => {
    if (Array.isArray(review?.photos) && review.photos.length > 0) {
      return review.photos.filter(Boolean);
    }
    return review?.photo ? [review.photo] : [];
  }, []);

  useEffect(() => {
    setRating(myReview?.rating || 0);
    setText(myReview?.text || "");
    setPhotos(getReviewPhotos(myReview));
    setIsEditing(false);
    setError("");
    setSuccess("");
  }, [checklist?.slug, getReviewPhotos, myReview, user?.id]);

  const resizeReviewPhoto = React.useCallback((file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const MAX_SIZE = 1280;
        let { width, height } = img;

        if (width > height && width > MAX_SIZE) {
          height *= MAX_SIZE / width;
          width = MAX_SIZE;
        } else if (height > MAX_SIZE) {
          width *= MAX_SIZE / height;
          height = MAX_SIZE;
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          reject(new Error("canvas_unavailable"));
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.82));
      };
      img.onerror = () => reject(new Error("image_load_failed"));
      img.src = loadEvent.target.result;
    };
    reader.onerror = () => reject(new Error("file_read_failed"));
    reader.readAsDataURL(file);
  }), []);

  if (!tripEnded && reviews.length === 0 && !canReview) {
    return null;
  }

  const handlePhotoChange = async (event) => {
    const freeSlots = Math.max(0, MAX_REVIEW_PHOTOS - photos.length);
    const files = Array.from(event.target.files || []).slice(0, freeSlots);
    if (files.length === 0) return;

    try {
      const nextPhotos = await Promise.all(files.map((file) => resizeReviewPhoto(file)));
      setPhotos((currentPhotos) => [...currentPhotos, ...nextPhotos].slice(0, MAX_REVIEW_PHOTOS));
      const selectedFilesCount = Array.from(event.target.files || []).length;
      if (selectedFilesCount > freeSlots) {
        setError(lang === "en" ? "You can attach up to 8 photos" : "Можно прикрепить до 8 фото");
      } else {
        setError("");
      }
    } catch {
      setError(lang === "en" ? "Failed to process photos" : "Не удалось обработать фотографии");
    } finally {
      event.target.value = "";
    }
  };

  const handleRemovePhoto = (photoIndex) => {
    setPhotos((currentPhotos) => currentPhotos.filter((_, index) => index !== photoIndex));
  };

  const handleSubmit = async () => {
    setError("");
    setSuccess("");

    if (!token) {
      setError(lang === "en" ? "Please log in to leave a review" : "Войдите в аккаунт, чтобы оставить отзыв");
      return;
    }
    if (rating < 1 || rating > 5) {
      setError(lang === "en" ? "Choose a rating from 1 to 5" : "Выберите оценку от 1 до 5");
      return;
    }
    if (text.trim().length < 10) {
      setError(lang === "en" ? "Review should be at least 10 characters long" : "Отзыв должен быть длиннее 10 символов");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_URL}/checklists/${checklist.slug}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          rating,
          text: text.trim(),
          photo: photos[0] || null,
          photos,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || (lang === "en" ? "Failed to save review" : "Не удалось сохранить отзыв"));
        return;
      }

      onReviewSaved(data);
      setIsEditing(false);
      setSuccess(lang === "en" ? "Review saved" : "Отзыв сохранён");
    } catch (submitError) {
      console.error(submitError);
      setError(lang === "en" ? "Network error while saving review" : "Ошибка сети при сохранении отзыва");
    } finally {
      setSaving(false);
    }
  };

  const handleStartEdit = () => {
    if (!myReview) return;
    setRating(myReview.rating || 0);
    setText(myReview.text || "");
    setPhotos(getReviewPhotos(myReview));
    setError("");
    setSuccess("");
    setIsEditing(true);
  };

  const handleDelete = async () => {
    if (!token || !checklist?.slug || !myReview || saving) return;
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete review" : "Удалить отзыв",
      message: lang === "en" ? "Your review will disappear from the trip page." : "Ваш отзыв исчезнет со страницы поездки.",
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) {
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`${API_URL}/checklists/${checklist.slug}/review`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const data = await readJsonSafely(response);
      if (!response.ok) {
        setError(data?.detail || (lang === "en" ? "Failed to delete review" : "Не удалось удалить отзыв"));
        return;
      }

      onReviewSaved(null, user?.id);
      setRating(0);
      setText("");
      setPhotos([]);
      setIsEditing(false);
      setSuccess(lang === "en" ? "Review deleted" : "Отзыв удалён");
    } catch (deleteError) {
      console.error(deleteError);
      setError(lang === "en" ? "Network error while deleting review" : "Ошибка сети при удалении отзыва");
    } finally {
      setSaving(false);
    }
  };

  const shouldShowReviewForm = tripEnded && canReview && (!myReview || isEditing);

  return (
    <section className="trip-reviews-section">
      <div className="trip-reviews-header">
        <div>
          <h3>{lang === "en" ? "Trip reviews" : "Отзывы о поездке"}</h3>
          <p>
            {reviews.length > 0
              ? (lang === "en"
                  ? `${reviews.length} review${reviews.length > 1 ? "s" : ""} • average ${averageRating}`
                  : `${reviews.length} ${reviews.length === 1 ? "отзыв" : reviews.length < 5 ? "отзыва" : "отзывов"} • средняя оценка ${averageRating}`)
              : (lang === "en" ? "No reviews yet" : "Пока нет отзывов")}
          </p>
        </div>
        {!tripEnded && (
          <span className="trip-reviews-chip">
            {lang === "en" ? "Available after the trip" : "Откроется после поездки"}
          </span>
        )}
      </div>

      {shouldShowReviewForm && (
        <div className="trip-review-form-card">
          <div className="trip-review-form-head">
            <div>
              <h4>{myReview ? (lang === "en" ? "Edit your review" : "Обновить отзыв") : (lang === "en" ? "Share your impression" : "Поделитесь впечатлением")}</h4>
              <p>{lang === "en" ? "Tell others how the trip went and add photos if you want." : "Расскажите, как прошла поездка, и при желании добавьте фото."}</p>
            </div>
            <div className="trip-review-stars" aria-label="rating">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  className={`trip-review-star ${rating >= star ? "active" : ""}`}
                  onClick={() => setRating(star)}
                >
                  ★
                </button>
              ))}
            </div>
          </div>

          <textarea
            className="trip-review-textarea"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              resizeTextareaToContent(event.currentTarget);
            }}
            placeholder={lang === "en" ? "What was great, what surprised you, what would you advise to others?" : "Что понравилось, что удивило, что посоветуете другим?"}
            rows={1}
          />

          <div className="trip-review-actions">
            <input
              ref={photoInputRef}
              type="file"
              accept="image/*"
              multiple
              className="visually-hidden-input"
              onChange={handlePhotoChange}
            />
            <button type="button" className="action-btn" onClick={() => photoInputRef.current?.click()}>
              {photos.length > 0 ? (lang === "en" ? "Add more photos" : "Добавить ещё фото") : (lang === "en" ? "Attach photos" : "Прикрепить фото")}
            </button>
            {myReview && (
              <button
                type="button"
                className="action-btn"
                onClick={() => {
                  setIsEditing(false);
                  setRating(myReview.rating || 0);
                  setText(myReview.text || "");
                  setPhotos(getReviewPhotos(myReview));
                  setError("");
                  setSuccess("");
                }}
              >
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
            )}
            <button type="button" className="action-btn primary" onClick={handleSubmit} disabled={saving}>
              {saving ? (lang === "en" ? "Saving..." : "Сохраняем...") : (myReview ? (lang === "en" ? "Update review" : "Обновить отзыв") : (lang === "en" ? "Publish review" : "Опубликовать отзыв"))}
            </button>
          </div>

          {photos.length > 0 && (
            <div className={`trip-review-photo-preview-grid photos-${Math.min(photos.length, 4)}`}>
              {photos.map((photo, index) => (
                <div key={`${photo}-${index}`} className="trip-review-photo-preview">
                  <button
                    type="button"
                    className="trip-review-photo-remove"
                    aria-label={lang === "en" ? `Remove photo ${index + 1}` : `Убрать фото ${index + 1}`}
                    onClick={() => handleRemovePhoto(index)}
                  >
                    ×
                  </button>
                  <img src={photo} alt={lang === "en" ? `Review preview ${index + 1}` : `Предпросмотр отзыва ${index + 1}`} />
                </div>
              ))}
            </div>
          )}

          {error && <div className="trip-review-feedback error">{error}</div>}
          {success && <div className="trip-review-feedback success">{success}</div>}
        </div>
      )}

      {tripEnded && !token && (
        <div className="trip-review-guest-hint">
          {lang === "en" ? "Log in after the trip to leave your own review." : "После поездки войдите в аккаунт, чтобы оставить свой отзыв."}
        </div>
      )}

      <div className="trip-reviews-list">
        {reviews.length === 0 ? (
          <div className="trip-reviews-empty">
            {lang === "en" ? "There are no public impressions for this trip yet." : "У этой поездки пока нет публичных впечатлений."}
          </div>
        ) : (
          reviews.map((review) => (
            <article key={review.id} className="trip-review-card">
              <div className="trip-review-card-head">
                <div className="trip-review-author">
                  <div className="trip-review-avatar">
                    {review.user?.avatar && (review.user.avatar.startsWith("data:image") || review.user.avatar.startsWith("http")) ? (
                      <img src={review.user.avatar} alt={review.user.username} />
                    ) : (
                      review.user?.avatar || review.user?.username?.charAt(0)?.toUpperCase() || "?"
                    )}
                  </div>
                  <div>
                    <div className="trip-review-username">{review.user?.username || "Traveler"}</div>
                    <div className="trip-review-date">
                      {review.created_at
                        ? new Date(review.created_at).toLocaleDateString(lang === "en" ? "en-US" : "ru-RU", { day: "numeric", month: "long", year: "numeric" })
                        : ""}
                    </div>
                  </div>
                </div>
                <div className="trip-review-rating">
                  <span className="trip-review-rating-stars">{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</span>
                </div>
              </div>

              {review.user?.id === user?.id && (
                <div className="trip-review-card-actions">
                  <button
                    type="button"
                    className="trip-review-icon-btn"
                    title={lang === "en" ? "Edit review" : "Редактировать отзыв"}
                    onClick={handleStartEdit}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="trip-review-icon-btn danger"
                    title={lang === "en" ? "Delete review" : "Удалить отзыв"}
                    onClick={handleDelete}
                  >
                    ×
                  </button>
                </div>
              )}

              <p className="trip-review-text">{review.text}</p>

              {getReviewPhotos(review).length > 0 && (
                <div className={`trip-review-photo-gallery photos-${Math.min(getReviewPhotos(review).length, 4)}`}>
                  {getReviewPhotos(review).map((photo, index) => (
                    <div key={`${review.id}-${index}`} className="trip-review-photo">
                      <img src={photo} alt={lang === "en" ? `Trip review photo ${index + 1}` : `Фото из поездки ${index + 1}`} />
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))
        )}
      </div>
    </section>
  );
});

const TripSettingsDropdown = React.memo(({
  label,
  options,
  value,
  onChange,
  placeholder,
  multiple = false,
  summary,
  placeholderActive = false,
  disabled = false,
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handlePointerDown = (event) => {
      const target = event.target;
      if (dropdownRef.current && !dropdownRef.current.contains(target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isOpen]);

  const resolvedSummary = multiple
    ? (summary || placeholder)
    : options.find((item) => item.id === value)?.label || placeholder;

  const showPlaceholder = multiple ? placeholderActive : !options.some((item) => item.id === value);

  return (
    <div className={`trip-settings-field ${className}`.trim()} ref={dropdownRef}>
      {label && <label className="section-label">{label}</label>}
      <button
        type="button"
        className={`trip-settings-dropdown-trigger ${isOpen ? "open" : ""}`}
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={disabled}
      >
        <span className={`trip-settings-dropdown-value ${showPlaceholder ? "placeholder" : ""}`}>
          {resolvedSummary}
        </span>
        <span className="trip-settings-chevron" aria-hidden="true">▾</span>
      </button>
      {isOpen && (
        <div className="trip-settings-dropdown-menu">
          {options.map((item) => {
            const isSelected = multiple
              ? Array.isArray(value) && value.includes(item.id)
              : value === item.id;

            return (
              <button
                key={item.id}
                type="button"
                className={`trip-settings-dropdown-option ${isSelected ? "active" : ""}`}
                onClick={() => {
                  onChange(item.id);
                  if (!multiple) setIsOpen(false);
                }}
              >
                <span>{item.label}</span>
                <span className="trip-settings-dropdown-check" aria-hidden="true">
                  {isSelected ? "✓" : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
});

const App = ({ page }) => {
  const { id } = useParams(); // slug из URL
  const navigate = useNavigate();
  const location = useLocation();

  const [lang, setLang] = useState("ru");
  const [theme, setTheme] = useState(resolveInitialTheme);
  const t = TRANSLATIONS[lang];
  const [showMobileNavMenu, setShowMobileNavMenu] = useState(false);
  const mobileNavMenuRef = useRef(null);

  const toggleLanguage = () => {
    setLang((current) => (current === "ru" ? "en" : "ru"));
  };

  const toggleThemeMode = () => {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  };

  useEffect(() => {
    if (!showMobileNavMenu) return undefined;

    const handlePointerDown = (event) => {
      if (mobileNavMenuRef.current && !mobileNavMenuRef.current.contains(event.target)) {
        setShowMobileNavMenu(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [showMobileNavMenu]);

  useEffect(() => {
    setShowMobileNavMenu(false);
  }, [location.pathname]);

  const [destinations, setDestinations] = useState([
    { id: 1, city: null, dates: { start: null, end: null }, transport: "plane" }
  ]);
  const [options, setOptions] = useState(() => normalizeTripOptions(INITIAL_TRIP_OPTIONS, { preserveEmptySelections: true }));
  const [result, setResult] = useState(null);
  const [checklistLoading, setChecklistLoading] = useState(() => Boolean(id));
  const [error, setError] = useState(null);
  const [originCity, setOriginCity] = useState("");
  const [returnTransport, setReturnTransport] = useState("plane");
  const [showAuth, setShowAuth] = useState(false);
  const [showForecast, setShowForecast] = useState(() =>
    typeof window === "undefined" ? true : window.innerWidth > 600
  ); // Collapsible forecast state
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("user");
    return safeParseJson(saved, null);
  });
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [isOffline, setIsOffline] = useState(() =>
    typeof navigator === "undefined" ? false : !navigator.onLine
  );
  const [usingStoredChecklist, setUsingStoredChecklist] = useState(false);
  const [hasPendingOfflineSync, setHasPendingOfflineSync] = useState(() =>
    Boolean(loadPendingChecklistSnapshot())
  );
  const [isSyncingOfflineChanges, setIsSyncingOfflineChanges] = useState(false);
  const [savedSlug, setSavedSlug] = useState(null);
  const [highlightedItineraryEventIds, setHighlightedItineraryEventIds] = useState([]);
  const latestResultRef = useRef(null);
  const persistPendingAfterRenderRef = useRef(false);

  // Состояние для чеклиста
  const [checkedItems, setCheckedItems] = useState({});
  // Состояние для удалённых вещей
  const [removedItems, setRemovedItems] = useState([]);
  const [addItemMode, setAddItemMode] = useState(false);
  const [newItem, setNewItem] = useState("");
  const [newItemQuantity, setNewItemQuantity] = useState(1);
  const [newItemCategory, setNewItemCategory] = useState("");
  const [showPackingModal, setShowPackingModal] = useState(false);
  const [showAdvancedTripSettings, setShowAdvancedTripSettings] = useState(false);
  const [activePackingProfile, setActivePackingProfile] = useState(() => normalizePackingProfile(DEFAULT_PACKING_PROFILE));
  const [packingProfileDraft, setPackingProfileDraft] = useState(() => normalizePackingProfile(DEFAULT_PACKING_PROFILE));
  const [packingProfileSaving, setPackingProfileSaving] = useState(false);
  const [newBaseItem, setNewBaseItem] = useState("");
  const [showBaseItemsModal, setShowBaseItemsModal] = useState(false);
  const [showCollaboratorsModal, setShowCollaboratorsModal] = useState(false);
  const [quantityEditor, setQuantityEditor] = useState(null);
  const [activeTab, setActiveTab] = useState("shared");
  const [activeParticipantId, setActiveParticipantId] = useState(null);
  const [showBaggageCreator, setShowBaggageCreator] = useState(false);
  const [newBaggageName, setNewBaggageName] = useState("");
  const [baggageBusy, setBaggageBusy] = useState(false);
  const [renamingBaggageId, setRenamingBaggageId] = useState(null);
  const [renamingBaggageName, setRenamingBaggageName] = useState("");
  const [accessOwner, setAccessOwner] = useState(null);
  const [accessEditorIds, setAccessEditorIds] = useState([]);
  const [moveItemDialog, setMoveItemDialog] = useState(null);
  const [moveItemBusy, setMoveItemBusy] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [appNotice, setAppNotice] = useState(null);
  const [inviteToken, setInviteToken] = useState("");
  const [followers, setFollowers] = useState([]);
  const [inviteBusyIds, setInviteBusyIds] = useState([]);
  const [inviteSentIds, setInviteSentIds] = useState([]);
  const [inviteAlreadyIds, setInviteAlreadyIds] = useState([]);
  const [collaboratorQuery, setCollaboratorQuery] = useState("");
  const [collaboratorResults, setCollaboratorResults] = useState([]);
  const [selectedCollaborators, setSelectedCollaborators] = useState([]);
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === "undefined" ? 1280 : window.innerWidth
  );

  // Computed: can current user view/edit different sections of this checklist?
  const isChecklistParticipant = Boolean(user && result && (result.user_id === user.id || (result.backpacks && result.backpacks.some(b => b.user_id === user.id))));
  const baggageParticipants = buildBaggageParticipants(result, user, lang);
  const checklistParticipantIds = getChecklistParticipantIds(result);
  const inviteBusyIdSet = new Set(inviteBusyIds);
  const inviteSentIdSet = new Set(inviteSentIds);
  const inviteAlreadyIdSet = new Set(inviteAlreadyIds);
  const activeParticipant = baggageParticipants.find((participant) => participant.userId === activeParticipantId) || null;
  const activeBaggage = activeTab !== "shared"
    ? (result?.backpacks || []).find((bag) => bag.id.toString() === activeTab)
    : null;
  const canEditActiveBaggage = Boolean(
    user &&
    activeBaggage &&
    canUserEditBaggage(activeBaggage, user.id, result?.backpacks || [], result)
  );
  const canEditCurrentSection = activeTab === "shared" ? isChecklistParticipant : canEditActiveBaggage;
  const canManageSelectedParticipant = Boolean(
    user &&
    activeParticipant &&
    (activeParticipant.userId === user.id || (activeParticipant.isChild && activeParticipant.ownerUserId === user.id))
  );
  const isOfflineEditAllowedForChecklist = isOfflineChecklistEditable(result, user?.id);
  const canMutateCurrentSection = canEditCurrentSection && (!isOffline || isOfflineEditAllowedForChecklist);
  const canUseOfflineChecklistReadOnly = Boolean(isOffline && result && !isOfflineEditAllowedForChecklist);
  const isChecklistRoute = Boolean(id);
  const showChecklistSkeleton = isChecklistRoute && checklistLoading && !result;
  const showChecklistErrorState = isChecklistRoute && !checklistLoading && !result && Boolean(error);
  const showHomeForm = !result && !showChecklistSkeleton && !showChecklistErrorState;
  const checklistSyncBadge = result ? (() => {
    if (isSyncingOfflineChanges) {
      return {
        tone: "syncing",
        text: lang === "en" ? "Syncing offline changes..." : "Синхронизируем офлайн-изменения...",
      };
    }
    if (isOffline && isOfflineEditAllowedForChecklist) {
      return {
        tone: "offline",
        text: hasPendingOfflineSync
          ? (lang === "en" ? "Offline mode: changes will sync later" : "Офлайн-режим: изменения синхронизируются позже")
          : (lang === "en" ? "Offline mode for your last checklist" : "Офлайн-режим для вашего последнего чеклиста"),
      };
    }
    if (canUseOfflineChecklistReadOnly) {
      return {
        tone: "readonly",
        text: lang === "en"
          ? "Offline read-only mode for shared checklist"
          : "Совместный чеклист офлайн доступен только для чтения",
      };
    }
    if (hasPendingOfflineSync) {
      return {
        tone: "pending",
        text: lang === "en" ? "Unsynced offline changes" : "Есть несинхронизированные офлайн-изменения",
      };
    }
    if (usingStoredChecklist) {
      return {
        tone: "cached",
        text: lang === "en" ? "Showing saved last checklist copy" : "Показываем сохраненную копию последнего чеклиста",
      };
    }
    return null;
  })() : null;
  const panelLoader = (
    <div className="loading-spinner-wrap" aria-hidden="true">
      <div className="loading-spinner" />
    </div>
  );
  const canReviewTrip = Boolean(
    user &&
    result &&
    isChecklistParticipant &&
    result.end_date &&
    result.end_date <= new Date().toISOString().slice(0, 10)
  );
  const moveDestinations = sortAllBackpacks(
    (result?.backpacks || []).filter(
      (baggage) =>
        baggage.id !== moveItemDialog?.sourceBackpackId &&
        user &&
        canUserEditBaggage(baggage, user.id, result?.backpacks || [], result)
    )
  ).map((baggage) => {
    const participant = baggage.child_profile_id
      ? baggageParticipants.find((entry) => entry.childProfileId === baggage.child_profile_id)
      : baggageParticipants.find((entry) => entry.userId === baggage.user_id);
    const ownerLabel = participant?.isCurrentUser
      ? (lang === "en" ? "Mine" : "Мне")
      : participant?.isChild
        ? participant.username
        : participant?.username || baggage.user?.username || (lang === "en" ? "Participant" : "Участнику");
    return {
      id: baggage.id,
      title: translateKnownBaggageName(baggage.name || getBaggageKindLabel(baggage, lang), lang),
      subtitle: `${ownerLabel} • ${getBaggageMetaLine(baggage, lang)}`,
      isMine: baggage.user_id === user?.id,
    };
  });
  const ownMoveDestinations = moveDestinations.filter((destination) => destination.isMine);
  const otherMoveDestinations = moveDestinations.filter((destination) => !destination.isMine);
  const isMobileChecklistView = viewportWidth <= 600;
  const resetAddItemDraft = () => {
    setNewItem("");
    setNewItemQuantity(1);
    setNewItemCategory("");
  };
  const toggleAddItemMode = () => {
    setAddItemMode((prev) => {
      if (prev) resetAddItemDraft();
      return !prev;
    });
  };
	  const canMoveQuantityEditorItem = quantityEditor
	    ? (quantityEditor.sectionKey === "shared"
	        ? (result?.backpacks?.length || 0) > 0
	        : (result?.backpacks?.length || 0) > 1)
	    : false;

  useEffect(() => {
    setInviteBusyIds([]);
    setInviteSentIds([]);
    setInviteAlreadyIds([]);
  }, [savedSlug]);

  const confirmResolverRef = React.useRef(null);

  const requestConfirm = React.useCallback(({ title, message, confirmLabel, cancelLabel, tone = "default" }) => (
    new Promise((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmDialog({
        title,
        message,
        confirmLabel,
        cancelLabel,
        tone,
      });
    })
  ), []);

  const closeConfirmDialog = React.useCallback((result) => {
    if (confirmResolverRef.current) {
      confirmResolverRef.current(result);
      confirmResolverRef.current = null;
    }
    setConfirmDialog(null);
  }, []);

  const pushAppNotice = React.useCallback((message, tone = "default") => {
    setAppNotice({ message, tone });
  }, []);

  useEffect(() => {
    if (!appNotice) return undefined;
    const timeoutId = window.setTimeout(() => {
      setAppNotice(null);
    }, 3200);
    return () => window.clearTimeout(timeoutId);
  }, [appNotice]);

  const handleAuth = (userData, accessToken) => {
    setUser(userData);
    setToken(accessToken);
    localStorage.setItem("user", JSON.stringify(userData));
    localStorage.setItem("token", accessToken);
  };

  useEffect(() => {
    if (user) {
      localStorage.setItem("user", JSON.stringify(user));
    }
  }, [user]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const nextPackingProfile = normalizePackingProfile(user?.packing_profile || DEFAULT_PACKING_PROFILE);
    setActivePackingProfile(nextPackingProfile);
    setPackingProfileDraft(nextPackingProfile);
  }, [user]);

  useEffect(() => {
    const handleResize = () => {
      setViewportWidth(window.innerWidth);
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    setQuantityEditor(null);
  }, [activeTab, result?.slug]);

  useEffect(() => {
    setRenamingBaggageId(null);
    setRenamingBaggageName("");
  }, [activeParticipantId, activeTab]);

  useEffect(() => {
    if (!quantityEditor || isMobileChecklistView) return undefined;

    const handlePointerDown = (event) => {
      const target = event.target;
      if (
        target.closest(".quantity-editor-popover") ||
        target.closest(".item-progress-trigger")
      ) {
        return;
      }
      setQuantityEditor(null);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [isMobileChecklistView, quantityEditor]);

  const handleLogout = React.useCallback(() => {
    setUser(null);
    setToken(null);
    setHasPendingOfflineSync(false);
    setUsingStoredChecklist(false);
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    clearOfflineChecklistSnapshots();
    navigate('/');
  }, [navigate]);

  const authHeaders = React.useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : {}),
    [token]
  );

  const markChecklistPendingSync = React.useCallback(({ waitForNextRender = false, checklist = null } = {}) => {
    setHasPendingOfflineSync(true);

    if (waitForNextRender) {
      persistPendingAfterRenderRef.current = true;
      return;
    }

    const snapshot = checklist || latestResultRef.current;
    if (snapshot?.slug) {
      savePendingChecklistSnapshot(snapshot, user?.id ?? snapshot.user_id);
    }
  }, [user?.id]);

  const clearChecklistPendingSync = React.useCallback((checklist = null) => {
    const snapshot = checklist || latestResultRef.current;
    const pendingEntry = loadPendingChecklistSnapshot();
    if (pendingEntry?.slug && pendingEntry.slug !== snapshot?.slug) {
      return;
    }

    clearPendingChecklistSnapshot();
    setHasPendingOfflineSync(false);

    if (snapshot?.slug) {
      saveLastChecklistSnapshot(snapshot, user?.id ?? snapshot.user_id);
    }
  }, [user?.id]);

  const syncStoredChecklist = React.useCallback(async () => {
    if (isOffline || !authHeaders.Authorization) return false;

    const pendingEntry = loadPendingChecklistSnapshot();
    const pendingChecklist = pendingEntry?.checklist;
    if (!pendingChecklist?.slug) return false;

    if (!isOfflineChecklistEditable(pendingChecklist, user?.id ?? pendingChecklist.user_id)) {
      clearChecklistPendingSync(pendingChecklist);
      return false;
    }

    setIsSyncingOfflineChanges(true);

    try {
      const checklistResponse = await fetch(`${API_URL}/checklist/${pendingChecklist.slug}/state`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify(buildChecklistStatePayload(pendingChecklist)),
      });

      if (!checklistResponse.ok) {
        throw new Error("Checklist sync failed");
      }

      for (const backpack of pendingChecklist.backpacks || []) {
        if (!backpack?.id) continue;

        const backpackResponse = await fetch(`${API_URL}/backpacks/${backpack.id}/state`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders,
          },
          body: JSON.stringify(buildBackpackStatePayload(backpack)),
        });

        if (!backpackResponse.ok) {
          throw new Error("Backpack sync failed");
        }
      }

      const freshResponse = await fetch(`${API_URL}/checklist/${pendingChecklist.slug}`, {
        headers: authHeaders,
      });
      const freshChecklist = freshResponse.ok
        ? await freshResponse.json()
        : pendingChecklist;

      writeChecklistCache(pendingChecklist.slug, authHeaders, freshChecklist);
      clearChecklistPendingSync(freshChecklist);

      if ((savedSlug || id) === pendingChecklist.slug) {
        setResult(freshChecklist);
        setSavedSlug(pendingChecklist.slug);
        setUsingStoredChecklist(false);
      }

      return true;
    } catch (syncError) {
      console.error("Offline checklist sync error:", syncError);
      markChecklistPendingSync({ checklist: pendingChecklist });
      return false;
    } finally {
      setIsSyncingOfflineChanges(false);
    }
  }, [
    authHeaders,
    clearChecklistPendingSync,
    id,
    isOffline,
    markChecklistPendingSync,
    savedSlug,
    user?.id,
  ]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    latestResultRef.current = result;
  }, [result]);

  useEffect(() => {
    if (!result?.slug) return;

    const targetLang = lang === "en" ? "en" : "ru";
    const translationJobs = [];

    (result.items || []).forEach((item) => {
      const raw = String(item || "").trim();
      if (!raw) return;
      if (translateChecklistItemLabel(raw, targetLang, result.item_translations || {}) !== raw) return;
      if (detectItemTextLanguage(raw) === targetLang) return;
      translationJobs.push({ scope: "shared", item: raw });
    });

    (result.backpacks || []).forEach((backpack) => {
      (backpack?.items || []).forEach((item) => {
        const raw = String(item || "").trim();
        if (!raw) return;
        if (translateChecklistItemLabel(raw, targetLang, backpack?.item_translations || {}) !== raw) return;
        if (detectItemTextLanguage(raw) === targetLang) return;
        translationJobs.push({ scope: "backpack", backpackId: backpack.id, item: raw });
      });
    });

    if (translationJobs.length === 0) return;

    let cancelled = false;

    Promise.all(
      translationJobs.slice(0, 40).map(async (job) => {
        const translatedText = await requestChecklistItemTranslation(job.item, targetLang);
        if (!translatedText || translatedText === job.item) return null;
        const entry = buildChecklistItemTranslationEntry(
          job.item,
          translatedText,
          targetLang,
          detectItemTextLanguage(job.item)
        );
        if (!entry) return null;
        return { ...job, entry };
      })
    )
      .then((resolvedJobs) => {
        if (cancelled) return;
        const successfulJobs = resolvedJobs.filter(Boolean);
        if (successfulJobs.length === 0) return;

        let nextChecklistTranslations = normalizeItemTranslationMap(result.item_translations || {});
        let checklistChanged = false;
        const backpackUpdates = new Map();

        successfulJobs.forEach((job) => {
          if (job.scope === "shared") {
            const previous = JSON.stringify(nextChecklistTranslations[job.item] || {});
            nextChecklistTranslations = mergeItemTranslationEntry(nextChecklistTranslations, job.item, job.entry);
            if (previous !== JSON.stringify(nextChecklistTranslations[job.item] || {})) {
              checklistChanged = true;
            }
            return;
          }

          const backpack = (result.backpacks || []).find((entry) => entry.id === job.backpackId);
          const currentTranslations = backpackUpdates.get(job.backpackId)
            || normalizeItemTranslationMap(backpack?.item_translations || {});
          const nextTranslations = mergeItemTranslationEntry(currentTranslations, job.item, job.entry);
          backpackUpdates.set(job.backpackId, nextTranslations);
        });

        if (!checklistChanged && backpackUpdates.size === 0) return;

        setResult((prev) => {
          if (!prev) return prev;
          const next = { ...prev };
          if (checklistChanged) {
            next.item_translations = nextChecklistTranslations;
          }
          if (backpackUpdates.size > 0) {
            next.backpacks = (prev.backpacks || []).map((backpack) => (
              backpackUpdates.has(backpack.id)
                ? { ...backpack, item_translations: backpackUpdates.get(backpack.id) }
                : backpack
            ));
          }
          return next;
        });

        if (checklistChanged) {
          syncChecklist({ item_translations: nextChecklistTranslations });
        }
        backpackUpdates.forEach((itemTranslations, backpackId) => {
          syncBackpackItems(backpackId, { item_translations: itemTranslations });
        });
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
    // sync helpers are intentionally called with the latest result snapshot in this migration effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, result]);

  useEffect(() => {
    if (!result?.slug) return;

    saveLastChecklistSnapshot(result, user?.id ?? result.user_id);

    if (persistPendingAfterRenderRef.current) {
      savePendingChecklistSnapshot(result, user?.id ?? result.user_id);
      persistPendingAfterRenderRef.current = false;
      setHasPendingOfflineSync(true);
    }
  }, [result, user?.id]);

  useEffect(() => {
    if (isOffline || !token || !hasPendingOfflineSync) return;
    syncStoredChecklist();
  }, [hasPendingOfflineSync, isOffline, syncStoredChecklist, token]);

  useEffect(() => {
    if (!token) return undefined;

    let cancelled = false;
    fetch(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setUser(data);
          localStorage.setItem("user", JSON.stringify(data));
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [token]);

  const packingProfile = normalizePackingProfile(activePackingProfile);
  const hasVisibleSharedItems = false;
  const tripScenarioOptions = [
    { id: "city_break", label: lang === "en" ? "City walks" : "Город" },
    { id: "business_trip", label: lang === "en" ? "Work" : "Работа" },
    { id: "beach_escape", label: lang === "en" ? "Beach" : "Пляж" },
    { id: "outdoor_adventure", label: lang === "en" ? "Outdoor" : "Активный отдых" },
    { id: "winter_trip", label: lang === "en" ? "Winter" : "Зима" },
    { id: "romantic_getaway", label: lang === "en" ? "Date / romance" : "Романтика" },
    { id: "hiking", label: (t.activityHiking || "").trim() },
    { id: "workout", label: (t.activityWorkout || "").trim() },
    { id: "photo_content", label: (t.activityPhotoContent || "").trim() },
  ];
  const tripActivityOptions = tripScenarioOptions;
  const baggageFormatOptions = [
    { id: "carry_on", label: lang === "en" ? "Carry-on" : "Ручная кладь" },
    { id: "suitcase", label: lang === "en" ? "Suitcase" : "Чемодан" },
    { id: "suitcase_plus_carry_on", label: lang === "en" ? "Suitcase + carry-on" : "Чемодан + ручная кладь" },
    { id: "hiking_backpack", label: lang === "en" ? "Hiking backpack" : "Походный рюкзак" },
  ];
  const accommodationOptions = [
    { id: "hotel", label: (t.hotel || "").trim() },
    { id: "apartment", label: (t.apartment || "").trim() },
    { id: "hostel", label: (t.hostel || "").trim() },
    { id: "camping", label: (t.camping || "").trim() },
  ];
  const laundryOptions = [
    { id: "none", label: (t.noLaundry || "").trim() },
    { id: "limited", label: (t.limitedLaundry || "").trim() },
    { id: "easy", label: (t.easyLaundry || "").trim() },
  ];
  const packingStyleOptions = [
    { id: "light", label: (t.packingLight || "").trim() },
    { id: "balanced", label: (t.packingBalanced || "").trim() },
    { id: "prepared", label: (t.packingPrepared || "").trim() },
  ];
  const packingFactorOptions = [
    {
      id: "traveling_with_pet",
      label: lang === "en" ? "Traveling with pet" : "Путешествую с питомцем",
    },
    {
      id: "has_allergies",
      label: lang === "en" ? "There are allergies" : "Есть аллергии",
    },
  ];
  const selectedTripActivityLabels = tripActivityOptions
    .filter((activity) => options.trip_activities.includes(activity.id))
    .map((activity) => activity.label);
  const tripActivitiesSummary = selectedTripActivityLabels.length === 0
    ? (lang === "en" ? "Select scenarios" : "Выберите сценарии")
    : selectedTripActivityLabels.length <= 2
      ? selectedTripActivityLabels.join(", ")
      : `${selectedTripActivityLabels.slice(0, 2).join(", ")} +${selectedTripActivityLabels.length - 2}`;
  const selectedPackingFactorLabels = packingFactorOptions
    .filter((item) => Boolean(packingProfile[item.id]))
    .map((item) => item.label);
  const packingFactorsSummary = selectedPackingFactorLabels.length === 0
    ? (lang === "en" ? "Select extra factors" : "Выберите дополнительные факторы")
    : selectedPackingFactorLabels.length <= 2
      ? selectedPackingFactorLabels.join(", ")
      : `${selectedPackingFactorLabels.slice(0, 2).join(", ")} +${selectedPackingFactorLabels.length - 2}`;

  useEffect(() => {
    if (!token || !collaboratorQuery.trim()) {
      setCollaboratorResults((prev) => (prev.length ? [] : prev));
      return undefined;
    }

    const normalizedQuery = collaboratorQuery.trim();
    if (normalizedQuery.length < 2) {
      setCollaboratorResults((prev) => (prev.length ? [] : prev));
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetch(`${API_URL}/users/search?q=${encodeURIComponent(normalizedQuery)}`, {
          headers: authHeaders,
          signal: controller.signal,
        });
        if (!res.ok) {
          return;
        }
        const data = await res.json();
        const selectedIds = new Set(selectedCollaborators.map((item) => item.id));
        setCollaboratorResults(
          (data || []).filter((item) => item.id !== user?.id && !selectedIds.has(item.id))
        );
      } catch (e) {
        if (e.name !== "AbortError") {
          console.error("Collaborator search error:", e);
        }
      }
    }, 180);

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [authHeaders, collaboratorQuery, selectedCollaborators, token, user?.id]);

  useEffect(() => {
    if (!id) {
      setChecklistLoading(false);
      setUsingStoredChecklist(false);
      return undefined;
    }

    let isCancelled = false;

    const fetchChecklist = async () => {
      const cachedChecklist = getCachedChecklistSnapshot(id, authHeaders);
      const storedChecklist = loadLastChecklistSnapshot(id);

      setError(null);
      if (cachedChecklist) {
        setResult(cachedChecklist);
        setSavedSlug(id);
        setChecklistLoading(false);
        setUsingStoredChecklist(false);
      } else if (storedChecklist) {
        setResult(storedChecklist);
        setSavedSlug(id);
        setChecklistLoading(false);
        setUsingStoredChecklist(true);
      } else {
        setResult((prev) => (prev?.slug === id ? prev : null));
        setChecklistLoading(true);
        setUsingStoredChecklist(false);
      }

      try {
        const data = await fetchChecklistCached({ checklistId: id, authHeaders });
        if (isCancelled) return;
        setResult(data);
        setSavedSlug(id);
        setUsingStoredChecklist(false);
      } catch (e) {
        if (isCancelled) return;
        console.error(e);
        if (storedChecklist) {
          setResult(storedChecklist);
          setSavedSlug(id);
          setUsingStoredChecklist(true);
          setError(null);
        } else {
          setUsingStoredChecklist(false);
          setError("Ошибка при загрузке чеклиста");
        }
      } finally {
        if (!isCancelled) {
          setChecklistLoading(false);
        }
      }
    };

    fetchChecklist();
    return () => {
      isCancelled = true;
    };
  }, [authHeaders, id]);

  useEffect(() => {
    if (!result?.slug) return;
    writeChecklistCache(result.slug, authHeaders, result);
  }, [authHeaders, result]);

  useEffect(() => {
    if (!result?.trip_profile) return;
    setOptions((prev) => normalizeTripOptions({ ...prev, ...result.trip_profile }, { preserveEmptySelections: true }));
  }, [result?.slug, result?.trip_profile]);

  useEffect(() => {
    if (result && result.items && savedSlug) {
      setCheckedItems(
        buildCheckedItemsMap(
          result.items,
          result.checked_items,
          result.item_quantities || {},
          result.packed_quantities || {}
        )
      );
    }
  }, [result, savedSlug]);

  useEffect(() => {
    if (savedSlug) {
      setRemovedItems(result?.removed_items || []);
    }
  }, [result?.removed_items, savedSlug]);

  useEffect(() => {
    if (!result) return;

    const participants = buildBaggageParticipants(result, user, lang);
    if (participants.length === 0) {
      setActiveParticipantId(null);
      if (activeTab !== "shared") {
        setActiveTab("shared");
      }
      return;
    }

    const stillExists = participants.some((participant) => participant.userId === activeParticipantId);
    if (!stillExists) {
      const preferredParticipant =
        participants.find((participant) => participant.userId === user?.id) || participants[0];
      setActiveParticipantId(preferredParticipant.userId);
      return;
    }

    if (activeTab === "shared") {
      if (hasVisibleSharedItems) return;
      const preferredParticipant =
        participants.find((participant) => participant.userId === activeParticipantId)
        || participants.find((participant) => participant.userId === user?.id)
        || participants[0];
      const fallbackBaggage =
        preferredParticipant?.baggage.find((bp) => bp.is_default) || preferredParticipant?.baggage[0];
      if (fallbackBaggage) {
        setActiveParticipantId(preferredParticipant.userId);
        setActiveTab(fallbackBaggage.id.toString());
      }
      return;
    }

    const activeParticipantGroup = participants.find((participant) => participant.userId === activeParticipantId);
    const baggageStillExists = activeParticipantGroup?.baggage.some((bp) => bp.id.toString() === activeTab);
    if (!baggageStillExists) {
      const fallbackBaggage =
        activeParticipantGroup?.baggage.find((bp) => bp.is_default) || activeParticipantGroup?.baggage[0];
      setActiveTab(fallbackBaggage ? fallbackBaggage.id.toString() : "shared");
    }
  }, [result, user, activeParticipantId, activeTab, hasVisibleSharedItems, lang]);

  useEffect(() => {
    if (location.pathname === "/") {
      setSavedSlug(null);
      setResult(null);
      setChecklistLoading(false);
      setUsingStoredChecklist(false);
      setDestinations([{ id: 1, city: null, dates: { start: null, end: null } }]);
      setError(null);
    }
  }, [location.pathname]);

  const handleAddDestination = () => {
    setDestinations([
      ...destinations,
      { id: Date.now(), city: null, dates: { start: null, end: null }, transport: "plane" }
    ]);
  };

  const handleRemoveDestination = (id) => {
    if (destinations.length > 1) {
      setDestinations(destinations.filter(d => d.id !== id));
    }
  };

  const updateDestination = (id, field, value) => {
    setDestinations(prev => prev.map(d => {
      if (d.id === id) {
        return { ...d, [field]: value };
      }
      return d;
    }));
  };

  const updateTripOption = (key, value) => {
    setOptions((prev) => normalizeTripOptions({ ...prev, [key]: value }, { preserveEmptySelections: true }));
  };

  const updateTripPartyOptions = (nextParty) => {
    setOptions((prev) => normalizeTripOptions({ ...prev, ...normalizeTripParty(nextParty) }, { preserveEmptySelections: true }));
  };

  const updateActivePackingProfile = (patch) => {
    setActivePackingProfile((prev) => normalizePackingProfile({ ...prev, ...patch }));
  };

  const toggleTripActivity = (activityId) => {
    setOptions((prev) => {
      const currentActivities = normalizeTripActivities(prev.trip_activities);
      const nextActivities = currentActivities.includes(activityId)
        ? currentActivities.filter((item) => item !== activityId)
        : [...currentActivities, activityId];
      return normalizeTripOptions({ ...prev, trip_activities: nextActivities }, { preserveEmptySelections: true });
    });
  };

  const togglePackingFactor = (factorKey) => {
    updateActivePackingProfile({ [factorKey]: !packingProfile[factorKey] });
  };

  const handleAddBaseItem = () => {
    const normalizedItem = newBaseItem.trim();
    if (!normalizedItem) return;
    updateActivePackingProfile({
      always_include_items: normalizePackingProfileItems([...(packingProfile.always_include_items || []), normalizedItem]),
    });
    setNewBaseItem("");
  };

  const handleRemoveBaseItem = (itemToRemove) => {
    updateActivePackingProfile({
      always_include_items: packingProfile.always_include_items.filter((item) => item !== itemToRemove),
    });
  };

  const handleSavePackingProfile = async () => {
    if (!authHeaders.Authorization) {
      setShowAuth(true);
      return;
    }

    setPackingProfileSaving(true);
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({ packing_profile: packingProfileDraft }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось сохранить настройки");
      }
      setUser(data);
      localStorage.setItem("user", JSON.stringify(data));
      setActivePackingProfile(normalizePackingProfile(data?.packing_profile || DEFAULT_PACKING_PROFILE));
      setShowPackingModal(false);
    } catch (e) {
      alert(e.message || "Не удалось сохранить настройки");
    } finally {
      setPackingProfileSaving(false);
    }
  };

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    setSavedSlug(null);

    // Валидация
    const isValid = destinations.every(d => d.city && d.dates.start && d.dates.end);
    if (!isValid) {
      alert("Заполните все города и даты!");
      return;
    }

    try {
      const effectiveTripOptions = showAdvancedTripSettings
        ? options
        : normalizeTripOptions({
          ...DEFAULT_TRIP_OPTIONS,
          trip_note: options.trip_note,
          adults: options.adults,
          children_ages: options.children_ages,
          child_profiles: options.child_profiles,
        });
      const effectivePackingProfile = showAdvancedTripSettings
        ? packingProfile
        : normalizePackingProfile(DEFAULT_PACKING_PROFILE);
      const payload = {
        segments: destinations.map(d => ({
          city: d.city.fullName,
          start_date: d.dates.start,
          end_date: d.dates.end,
          trip_type: effectiveTripOptions.trip_type,
          transport: d.transport || "plane",
        })),
        trip_activities: effectiveTripOptions.trip_activities,
        baggage_format: effectiveTripOptions.baggage_format,
        accommodation_type: showAdvancedTripSettings ? effectiveTripOptions.accommodation_type : "",
        laundry_access: effectiveTripOptions.laundry_access,
        packing_style: effectiveTripOptions.packing_style,
        trip_note: effectiveTripOptions.trip_note.trim(),
        gender: "unspecified",
        traveling_with_pet: effectivePackingProfile.traveling_with_pet,
        has_allergies: effectivePackingProfile.has_allergies,
        traveling_with_children: effectivePackingProfile.traveling_with_children || effectiveTripOptions.children_ages.length > 0,
        adults: effectiveTripOptions.adults,
        children_ages: effectiveTripOptions.children_ages,
        child_profiles: effectiveTripOptions.child_profiles,
        infants_count: effectiveTripOptions.children_ages.filter((age) => age < 2).length,
        participant_user_ids: selectedCollaborators.map((person) => person.id),
        language: lang,
        origin_city: originCity?.fullName || originCity || "",
        return_transport: returnTransport,
      };

      const res = await fetch(`${API_URL}/generate-multi-city`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errorData = await res.json();
        setError(errorData.detail || "Ошибка при генерации списка");
        return;
      }

      const data = await res.json();

      // Проверяем наличие daily_forecast в ответе
      if (!data.daily_forecast) {
        console.warn("daily_forecast отсутствует в ответе сервера", data);
      }

      setResult(data);
      setSavedSlug(data.slug || null);

      if (data?.slug && token && selectedCollaborators.length > 0) {
        await Promise.all(
          selectedCollaborators.map(async (collaborator) => {
            try {
              await fetch(`${API_URL}/checklists/${data.slug}/invite/${collaborator.id}`, {
                method: "POST",
                headers: authHeaders,
              });
            } catch (inviteError) {
              console.error("Invite collaborator error:", inviteError);
            }
          })
        );
      }

      setCollaboratorQuery("");
      setCollaboratorResults([]);
      setSelectedCollaborators([]);
    } catch {
      setError("Ошибка при запросе к серверу");
    }
  };

  const syncChecklist = async (payload) => {
    try {
      if (!authHeaders.Authorization || !savedSlug) return;
      if (isOffline) {
        markChecklistPendingSync({ waitForNextRender: true });
        return;
      }
      const response = await fetch(`${API_URL}/checklist/${savedSlug}/state`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error("Checklist sync failed");
      }
      clearChecklistPendingSync();
    } catch (e) {
      console.error("Checklist sync error:", e);
      markChecklistPendingSync({ checklist: latestResultRef.current });
    }
  };

  const syncBackpackItems = async (backpackId, payload) => {
    try {
      if (!authHeaders.Authorization) return;
      if (isOffline) {
        markChecklistPendingSync({ waitForNextRender: true });
        return;
      }
      const response = await fetch(`${API_URL}/backpacks/${backpackId}/state`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error("Backpack sync failed");
      }
      clearChecklistPendingSync();
    } catch (e) {
      console.error("Backpack sync error:", e);
      markChecklistPendingSync({ checklist: latestResultRef.current });
    }
  };

  const ensureChecklistEditAllowed = () => {
    if (!canEditCurrentSection) return false;
    if (!isOffline || isOfflineEditAllowedForChecklist) return true;

    alert(
      lang === "en"
        ? "Offline editing is available only for your personal last checklist. Shared checklists stay read-only offline."
        : "Офлайн-редактирование доступно только для вашего личного последнего чеклиста. Совместные чеклисты офлайн открываются только для чтения."
    );
    return false;
  };

  const handleQuantityStateChange = (item, nextNeededQuantity, nextPackedQuantity) => {
    if (!ensureChecklistEditAllowed()) return;
    const quantity = Math.max(1, Number(nextNeededQuantity) || 1);
    const packed = Math.max(0, Math.min(quantity, Number(nextPackedQuantity) || 0));

    if (activeTab === "shared") {
      const nextQuantities = setItemQuantityInMap(result?.item_quantities || {}, item, quantity);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, item, packed);
      const nextCheckedMap = buildCheckedItemsMap(result?.items || [], result?.checked_items || [], nextQuantities, nextPacked);
      const nextCheckedItems = Object.keys(nextCheckedMap).filter((entry) => nextCheckedMap[entry]);
      setCheckedItems(buildCheckedItemsMap(result?.items || [], nextCheckedItems, nextQuantities, nextPacked));
      setResult((prev) => ({
        ...prev,
        checked_items: nextCheckedItems,
        item_quantities: nextQuantities,
        packed_quantities: nextPacked,
      }));
      syncChecklist({ checked_items: nextCheckedItems, item_quantities: nextQuantities, packed_quantities: nextPacked });
      return;
    }

    setResult((prev) => {
      const next = { ...prev };
      const bp = next.backpacks?.find((bag) => bag.id.toString() === activeTab);
      if (bp) {
        bp.item_quantities = setItemQuantityInMap(bp.item_quantities || {}, item, quantity);
        bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, item, packed);
        bp.checked_items = (bp.items || []).filter(
          (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
        );
        syncBackpackItems(activeTab, {
          checked_items: bp.checked_items,
          item_quantities: bp.item_quantities,
          packed_quantities: bp.packed_quantities,
        });
      }
      return next;
    });
  };

  const toggleQuantityEditor = (item, neededQuantity, packedQuantity) => {
    const sectionKey = activeTab;
    setQuantityEditor((prev) => {
      if (prev?.item === item && prev?.sectionKey === sectionKey) {
        return null;
      }
      return {
        item,
        sectionKey,
        needed: Math.max(1, Number(neededQuantity) || 1),
        packed: Math.max(0, Math.min(Number(neededQuantity) || 1, Number(packedQuantity) || 0)),
      };
    });
  };

  const updateQuantityEditorDraft = (field, nextValue) => {
    setQuantityEditor((prev) => {
      if (!prev) return prev;
      if (field === "needed") {
        const needed = Math.max(1, Number(nextValue) || 1);
        return {
          ...prev,
          needed,
          packed: Math.min(prev.packed, needed),
        };
      }

      const packed = Math.max(0, Math.min(prev.needed, Number(nextValue) || 0));
      return {
        ...prev,
        packed,
      };
    });
  };

  const applyQuantityEditor = () => {
    if (!quantityEditor) return;
    handleQuantityStateChange(quantityEditor.item, quantityEditor.needed, quantityEditor.packed);
    setQuantityEditor(null);
  };

  const handleQuickPackedChange = (item, delta) => {
    if (!ensureChecklistEditAllowed()) return;
    const targetNeeded = activeTab === "shared"
      ? getItemQuantity(result?.item_quantities || {}, item)
      : getItemQuantity(
          result?.backpacks?.find((bag) => bag.id.toString() === activeTab)?.item_quantities || {},
          item
        );
    const targetPacked = activeTab === "shared"
      ? getPackedQuantity(result?.packed_quantities || {}, item)
      : getPackedQuantity(
          result?.backpacks?.find((bag) => bag.id.toString() === activeTab)?.packed_quantities || {},
          item
        );
    handleQuantityStateChange(item, targetNeeded, targetPacked + delta);
  };

  const handleCheck = (item) => {
    if (!ensureChecklistEditAllowed()) return;
    if (activeTab === "shared") {
      const needed = getItemQuantity(result?.item_quantities || {}, item);
      const currentPacked = getPackedQuantity(result?.packed_quantities || {}, item);
      const nextPacked = setPackedQuantityInMap(
        result?.packed_quantities || {},
        item,
        currentPacked >= needed ? 0 : needed
      );
      const nextCheckedItems = (result?.items || []).filter(
        (existingItem) => getPackedQuantity(nextPacked, existingItem) >= getItemQuantity(result?.item_quantities || {}, existingItem)
      );
      const nextCheckedMap = buildCheckedItemsMap(result?.items || [], nextCheckedItems, result?.item_quantities || {}, nextPacked);
      setCheckedItems(nextCheckedMap);
      setResult((prev) => ({ ...prev, checked_items: nextCheckedItems, packed_quantities: nextPacked }));
      syncChecklist({ checked_items: nextCheckedItems, packed_quantities: nextPacked });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          const needed = getItemQuantity(bp.item_quantities || {}, item);
          const currentPacked = getPackedQuantity(bp.packed_quantities || {}, item);
          bp.packed_quantities = setPackedQuantityInMap(
            bp.packed_quantities || {},
            item,
            currentPacked >= needed ? 0 : needed
          );
          bp.checked_items = (bp.items || []).filter(
            (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
          );
          syncBackpackItems(activeTab, {
            checked_items: bp.checked_items,
            packed_quantities: bp.packed_quantities,
          });
        }
        return next;
      });
    }
  };

  const handleRemoveItem = (item) => {
    if (!ensureChecklistEditAllowed()) return;
    if (activeTab === "shared") {
      const newRemoved = [...removedItems, item];
      setRemovedItems(newRemoved);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, item, 0);
      const nextCheckedItems = (result?.items || []).filter(
        (existingItem) => getPackedQuantity(nextPacked, existingItem) >= getItemQuantity(result?.item_quantities || {}, existingItem)
      );
      setCheckedItems(buildCheckedItemsMap(result?.items || [], nextCheckedItems, result?.item_quantities || {}, nextPacked));
      setResult((prev) => ({ ...prev, checked_items: nextCheckedItems, packed_quantities: nextPacked }));
      syncChecklist({ removed_items: newRemoved, checked_items: nextCheckedItems, packed_quantities: nextPacked });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          bp.removed_items = [...bp.removed_items, item];
          bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, item, 0);
          bp.checked_items = (bp.items || []).filter(
            (existingItem) => getPackedQuantity(bp.packed_quantities || {}, existingItem) >= getItemQuantity(bp.item_quantities || {}, existingItem)
          );
          syncBackpackItems(activeTab, {
            removed_items: bp.removed_items,
            checked_items: bp.checked_items,
            packed_quantities: bp.packed_quantities,
          });
        }
        return next;
      });
    }
  };

  const resetChecklist = () => {
    if (!ensureChecklistEditAllowed()) return;
    if (activeTab === "shared") {
      const reset = {};
      result.items.forEach(item => { reset[item] = false; });
      setCheckedItems(reset);
      setResult((prev) => ({ ...prev, checked_items: [], packed_quantities: {} }));
      syncChecklist({ checked_items: [], packed_quantities: {} });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        if (bp) {
          bp.checked_items = [];
          bp.packed_quantities = {};
          syncBackpackItems(activeTab, { checked_items: [], packed_quantities: {} });
        }
        return next;
      });
    }
  };

  const handleAddItem = () => {
    if (!ensureChecklistEditAllowed()) return;
    const normalizedItem = newItem.trim();
    if (!normalizedItem) return;
    const resolvedQuantity = Math.max(1, Number(newItemQuantity) || 1);
    const sourceLang = detectItemTextLanguage(normalizedItem);
    const targetLang = sourceLang === "ru" ? "en" : "ru";
    const targetSectionKey = activeTab;
    requestChecklistItemTranslation(normalizedItem, targetLang).then((translatedText) => {
      if (!translatedText || translatedText === normalizedItem) return;
      const translationEntry = buildChecklistItemTranslationEntry(
        normalizedItem,
        translatedText,
        targetLang,
        sourceLang
      );
      if (!translationEntry) return;
      cacheChecklistItemTranslation({
        label: translatedText,
        translatedText: normalizedItem,
        targetLang: sourceLang,
        sourceLang: targetLang,
      });

      if (targetSectionKey === "shared") {
        const nextTranslations = mergeItemTranslationEntry(
          latestResultRef.current?.item_translations || {},
          normalizedItem,
          translationEntry
        );
        setResult((prev) => (prev ? { ...prev, item_translations: nextTranslations } : prev));
        syncChecklist({ item_translations: nextTranslations });
        return;
      }

      const currentBackpack = (latestResultRef.current?.backpacks || []).find(
        (bag) => bag.id.toString() === targetSectionKey
      );
      const nextTranslations = mergeItemTranslationEntry(
        currentBackpack?.item_translations || {},
        normalizedItem,
        translationEntry
      );
      setResult((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          backpacks: (prev.backpacks || []).map((bag) => (
            bag.id.toString() === targetSectionKey
              ? { ...bag, item_translations: nextTranslations }
              : bag
          )),
        };
      });
      syncBackpackItems(targetSectionKey, { item_translations: nextTranslations });
    }).catch(() => {});
    if (activeTab === "shared") {
      const resolvedCategory = newItemCategory || inferItemCategory(normalizedItem, lang, result?.item_categories || {});
      if (result.items.includes(normalizedItem)) {
        if (removedItems.includes(normalizedItem)) {
          const nextRemoved = removedItems.filter((existing) => existing !== normalizedItem);
          const nextQuantities = setItemQuantityInMap(
            result?.item_quantities || {},
            normalizedItem,
            getItemQuantity(result?.item_quantities || {}, normalizedItem) || resolvedQuantity
          );
          const nextPacked = setPackedQuantityInMap(
            result?.packed_quantities || {},
            normalizedItem,
            getPackedQuantity(result?.packed_quantities || {}, normalizedItem)
          );
          const nextCategories = setItemCategoryInMap(result?.item_categories || {}, normalizedItem, resolvedCategory);
          setRemovedItems(nextRemoved);
          setResult((prev) => ({ ...prev, item_quantities: nextQuantities, packed_quantities: nextPacked, item_categories: nextCategories }));
          syncChecklist({ removed_items: nextRemoved, item_quantities: nextQuantities, packed_quantities: nextPacked, item_categories: nextCategories });
        }
        resetAddItemDraft();
        setAddItemMode(false);
        return;
      }
      const newItems = [...result.items, normalizedItem];
      const nextQuantities = setItemQuantityInMap(result?.item_quantities || {}, normalizedItem, resolvedQuantity);
      const nextPacked = setPackedQuantityInMap(result?.packed_quantities || {}, normalizedItem, 0);
      const nextCategories = setItemCategoryInMap(result?.item_categories || {}, normalizedItem, resolvedCategory);
      setResult(prev => ({ ...prev, items: newItems, item_quantities: nextQuantities, packed_quantities: nextPacked, item_categories: nextCategories }));
      syncChecklist({ items: newItems, item_quantities: nextQuantities, packed_quantities: nextPacked, item_categories: nextCategories });
    } else {
      setResult(prev => {
        const next = { ...prev };
        const bp = next.backpacks?.find(b => b.id.toString() === activeTab);
        const resolvedCategory = newItemCategory || inferItemCategory(normalizedItem, lang, bp?.item_categories || {});
        if (bp && bp.items.includes(normalizedItem)) {
          if (bp.removed_items.includes(normalizedItem)) {
            bp.removed_items = bp.removed_items.filter((existing) => existing !== normalizedItem);
            bp.item_quantities = setItemQuantityInMap(
              bp.item_quantities || {},
              normalizedItem,
              getItemQuantity(bp.item_quantities || {}, normalizedItem) || resolvedQuantity
            );
            bp.packed_quantities = setPackedQuantityInMap(
              bp.packed_quantities || {},
              normalizedItem,
              getPackedQuantity(bp.packed_quantities || {}, normalizedItem)
            );
            bp.item_categories = setItemCategoryInMap(bp.item_categories || {}, normalizedItem, resolvedCategory);
            syncBackpackItems(activeTab, {
              removed_items: bp.removed_items,
              item_quantities: bp.item_quantities,
              packed_quantities: bp.packed_quantities,
              item_categories: bp.item_categories,
            });
          }
          return next;
        }
        if (bp) {
          bp.items = [...bp.items, normalizedItem];
          bp.item_quantities = setItemQuantityInMap(bp.item_quantities || {}, normalizedItem, resolvedQuantity);
          bp.packed_quantities = setPackedQuantityInMap(bp.packed_quantities || {}, normalizedItem, 0);
          bp.item_categories = setItemCategoryInMap(bp.item_categories || {}, normalizedItem, resolvedCategory);
          syncBackpackItems(activeTab, {
            items: bp.items,
            item_quantities: bp.item_quantities,
            packed_quantities: bp.packed_quantities,
            item_categories: bp.item_categories,
          });
        }
        return next;
      });
    }
    resetAddItemDraft();
    setAddItemMode(false);
  };

  const openMoveItemDialog = (item, sourceBackpackId = null) => {
    setMoveItemDialog({
      item,
      sourceBackpackId,
      targetBackpackId: null,
    });
  };

  const handleConfirmMoveItem = async () => {
    if (!moveItemDialog?.item || !moveItemDialog?.targetBackpackId || !savedSlug || !authHeaders.Authorization) return;
    if (isOffline) {
      alert(lang === "en" ? "Move item is unavailable offline" : "Перемещение вещей офлайн недоступно");
      return;
    }

    setMoveItemBusy(true);
    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/transfer-item`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({
          item: moveItemDialog.item,
          source_backpack_id: moveItemDialog.sourceBackpackId,
          target_backpack_id: moveItemDialog.targetBackpackId,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Не удалось перенести вещь");
      }
      setResult(data);
      setMoveItemDialog(null);
    } catch (e) {
      alert(e.message || "Не удалось перенести вещь");
    } finally {
      setMoveItemBusy(false);
    }
  };

  const selectParticipant = (participantUserId) => {
    setActiveParticipantId(participantUserId);
    setShowBaggageCreator(false);
    setNewBaggageName("");
    const participant = baggageParticipants.find((entry) => entry.userId === participantUserId);
    const fallbackBaggage = participant?.baggage.find((bp) => bp.is_default) || participant?.baggage[0];
    setActiveTab(fallbackBaggage ? fallbackBaggage.id.toString() : "shared");
  };

  const handleCreateBaggage = async () => {
    const name = newBaggageName.trim();
    if (!name || !savedSlug || !activeParticipant || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/baggage`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          user_id: activeParticipant.isChild ? user.id : activeParticipant.userId,
          child_profile_id: activeParticipant.isChild ? activeParticipant.childProfileId : null,
          name,
          kind: guessBaggageKind(name),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to create baggage" : "Не удалось создать багаж"));
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks([...(prev.backpacks || []), data]),
      }));
      setActiveParticipantId(data.child_profile_id ? `child:${data.child_profile_id}` : data.user_id);
      setActiveTab(data.id.toString());
      setNewBaggageName("");
      setShowBaggageCreator(false);
    } catch (e) {
      alert(e.message || (lang === "en" ? "Failed to create baggage" : "Не удалось создать багаж"));
    } finally {
      setBaggageBusy(false);
    }
  };

  const handleDeleteBaggage = async (baggage) => {
    if (!savedSlug || !authHeaders.Authorization) return;
    const confirmed = await requestConfirm({
      title: lang === "en" ? "Delete baggage" : "Удалить багаж",
      message: lang === "en"
        ? `"${translateKnownBaggageName(baggage.name || getBaggageKindLabel(baggage, lang), lang)}" will be removed from this trip.`
        : `«${baggage.name || "Багаж"}» будет удалён из этой поездки.`,
      confirmLabel: lang === "en" ? "Delete" : "Удалить",
      cancelLabel: lang === "en" ? "Cancel" : "Отмена",
      tone: "danger",
    });
    if (!confirmed) return;

    setBaggageBusy(true);
    try {
      let res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      let data = await res.json();
      if (!res.ok && data?.detail === "Сначала освободите багаж от вещей" && getBaggageVisibleItemCount(baggage) === 0) {
        const cleanupRes = await fetch(`${API_URL}/backpacks/${baggage.id}/state`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify(clearBaggageStatePayload(baggage)),
        });
        if (cleanupRes.ok) {
          setResult((prev) => ({
            ...prev,
            backpacks: (prev.backpacks || []).map((bp) => (
              bp.id === baggage.id
                ? { ...bp, ...clearBaggageStatePayload(bp) }
                : bp
            )),
          }));

          res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
            method: "DELETE",
            headers: authHeaders,
          });
          data = await res.json();
        }
      }
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to delete baggage" : "Не удалось удалить багаж"));
      }

      setResult((prev) => {
        const nextBackpacks = (prev.backpacks || []).filter((bp) => bp.id !== baggage.id);
        return {
          ...prev,
          hidden_sections: (prev.hidden_sections || []).filter((section) => section !== `backpack:${baggage.id}`),
          backpacks: nextBackpacks,
        };
      });

      const participant = baggage.child_profile_id
        ? baggageParticipants.find((entry) => entry.childProfileId === baggage.child_profile_id)
        : baggageParticipants.find((entry) => entry.userId === baggage.user_id);
      const nextBaggage = participant?.baggage.filter((bp) => bp.id !== baggage.id);
      const fallback = nextBaggage?.find((bp) => bp.is_default) || nextBaggage?.[0];
      setActiveTab(fallback ? fallback.id.toString() : "shared");
    } catch (e) {
      pushAppNotice(
        e.message || (lang === "en" ? "Failed to delete baggage" : "Не удалось удалить багаж"),
        "error"
      );
    } finally {
      setBaggageBusy(false);
    }
  };

  const handleSetDefaultBaggage = async (baggage) => {
    if (!savedSlug || !authHeaders.Authorization || baggage.is_default) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ is_default: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to make baggage primary" : "Не удалось сделать багаж основным"));
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks(
          (prev.backpacks || []).map((bp) => (
            bp.user_id === data.user_id && (bp.child_profile_id || null) === (data.child_profile_id || null)
              ? {
                  ...bp,
                  ...(bp.id === data.id ? data : {}),
                  is_default: bp.id === data.id,
                }
              : bp
          ))
        ),
      }));
      setActiveTab(data.id.toString());
    } catch (e) {
      alert(e.message || (lang === "en" ? "Failed to make baggage primary" : "Не удалось сделать багаж основным"));
    } finally {
      setBaggageBusy(false);
    }
  };

  const startRenameBaggage = (baggage) => {
    setRenamingBaggageId(baggage.id);
    setRenamingBaggageName(baggage.name || "");
  };

  const handleRenameBaggage = async (baggage) => {
    const nextName = renamingBaggageName.trim();
    if (!nextName || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${baggage.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          name: nextName,
          kind: guessBaggageKind(nextName),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to rename baggage" : "Не удалось переименовать багаж"));
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks((prev.backpacks || []).map((bp) => (bp.id === data.id ? data : bp))),
      }));
      setRenamingBaggageId(null);
      setRenamingBaggageName("");
    } catch (e) {
      alert(e.message || (lang === "en" ? "Failed to rename baggage" : "Не удалось переименовать багаж"));
    } finally {
      setBaggageBusy(false);
    }
  };

  const openBaggageAccess = (participant) => {
    const anchorBaggage =
      participant?.baggage?.find((baggage) => baggage.is_default) || participant?.baggage?.[0];
    if (!participant || !anchorBaggage) return;

    setAccessOwner({
      userId: anchorBaggage.user_id,
      displayName: participant.isChild
        ? (lang === "en" ? `Child's baggage: ${participant.username}` : `Багаж ребенка: ${participant.username}`)
        : participant.isCurrentUser ? (lang === "en" ? "My baggage" : "Мой багаж") : (lang === "en" ? `${participant.username}'s baggage` : `Багаж ${participant.username}`),
      anchorBackpackId: anchorBaggage.id,
    });
    setAccessEditorIds(getOwnerBaggageEditorIds(result?.backpacks || [], anchorBaggage.user_id, anchorBaggage));
  };

  const handleToggleBaggageEditor = (participantUserId) => {
    setAccessEditorIds((prev) => (
      prev.includes(participantUserId)
        ? prev.filter((id) => id !== participantUserId)
        : [...prev, participantUserId]
    ));
  };

  const handleSaveBaggageAccess = async () => {
    if (!accessOwner || !authHeaders.Authorization) return;

    setBaggageBusy(true);
    try {
      const res = await fetch(`${API_URL}/baggage/${accessOwner.anchorBackpackId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ editor_user_ids: accessEditorIds }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || (lang === "en" ? "Failed to update access" : "Не удалось обновить доступ"));
      }

      setResult((prev) => ({
        ...prev,
        backpacks: sortAllBackpacks((prev.backpacks || []).map((bp) => (
          bp.user_id === accessOwner.userId
            ? { ...bp, editor_user_ids: data.editor_user_ids || accessEditorIds }
            : bp
        ))),
      }));
      setAccessOwner(null);
      setAccessEditorIds([]);
    } catch (e) {
      alert(e.message || (lang === "en" ? "Failed to update access" : "Не удалось обновить доступ"));
    } finally {
      setBaggageBusy(false);
    }
  };

  const addCollaborator = (person) => {
    setSelectedCollaborators((prev) => (
      prev.some((item) => item.id === person.id) ? prev : [...prev, person]
    ));
    setCollaboratorQuery("");
    setCollaboratorResults([]);
  };

  const removeCollaborator = (userId) => {
    setSelectedCollaborators((prev) => prev.filter((item) => item.id !== userId));
  };

  const handleToggleSectionVisibility = async (section) => {
    if (!result || !authHeaders.Authorization) return;

    const isHidden = result.hidden_sections?.includes(section);
    let newHidden = [];
    if (isHidden) {
      newHidden = result.hidden_sections.filter(s => s !== section);
    } else {
      newHidden = [...(result.hidden_sections || []), section];
    }

    try {
      const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/hidden-sections`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ hidden_sections: newHidden })
      });
      if (res.ok) {
        const data = await res.json();
        setResult(prev => ({ ...prev, hidden_sections: data.hidden_sections }));
      }
    } catch (e) {
      console.error("Error toggling section visibility:", e);
    }
  };

  const handleReviewSaved = (savedReview, removedUserId = null) => {
    setResult((prev) => {
      if (!prev) return prev;
      const remainingReviews = (prev.reviews || []).filter(
        (review) => review.user?.id !== (removedUserId ?? savedReview?.user?.id)
      );
      if (!savedReview) {
        return {
          ...prev,
          reviews: remainingReviews,
        };
      }
      return {
        ...prev,
        reviews: [savedReview, ...remainingReviews].sort(
          (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
        ),
      };
    });
  };

  const handleChecklistUpdated = (updatedChecklist) => {
    if (!updatedChecklist) return;

    const nextSlug = updatedChecklist.slug || savedSlug;
    const nextCheckedItems = buildCheckedItemsMap(
      updatedChecklist.items || [],
      updatedChecklist.checked_items || [],
      updatedChecklist.item_quantities || {},
      updatedChecklist.packed_quantities || {}
    );
    const nextRemovedItems = updatedChecklist.removed_items || [];

    setSavedSlug(nextSlug || null);
    setCheckedItems(nextCheckedItems);
    setRemovedItems(nextRemovedItems);
    setActiveTab("shared");
    setResult(updatedChecklist);
  };

  const handlePlanApplied = (createdEventIds = []) => {
    const nextIds = (Array.isArray(createdEventIds) ? createdEventIds : []).filter((value) => Number.isInteger(value));
    if (nextIds.length === 0) return;
    setHighlightedItineraryEventIds(nextIds);
    window.setTimeout(() => {
      setHighlightedItineraryEventIds((current) => (
        current.every((id) => nextIds.includes(id)) ? [] : current
      ));
    }, 12000);
  };

  const formatDate = (isoDate) => {
    const d = new Date(isoDate);
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}.${month}.${year}`;
  };

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-logo" onClick={() => navigate("/")}>
          <img
            src={theme === "light" ? "/luggify-logo-light.svg" : "/luggify-logo.svg"}
            alt=""
            className="navbar-logo-mark"
            aria-hidden="true"
          />
          <span className="navbar-logo-text">LUGGIFY</span>
        </div>
        <div className="navbar-center navbar-search-desktop">
          <NavbarUserSearch
            lang={lang}
            navigate={navigate}
            currentUsername={user?.username || ""}
          />
        </div>
        <div className="navbar-user">
          <div className="navbar-locale-tools">
            <div className="locale-cluster">
              <div className="language-switcher" role="group" aria-label={lang === "en" ? "Language" : "Язык"}>
                <button
                  className={`lang-btn ${lang === "ru" ? "active" : ""}`}
                  onClick={() => setLang("ru")}
                >RU</button>
                <button
                  className={`lang-btn ${lang === "en" ? "active" : ""}`}
                  onClick={() => setLang("en")}
                >EN</button>
              </div>
              <div className="theme-switcher" role="group" aria-label={lang === "en" ? "Color theme" : "Цветовая тема"}>
                <button
                  className={`theme-btn ${theme === "light" ? "active" : ""}`}
                  onClick={() => setTheme("light")}
                  aria-label={lang === "en" ? "Light theme" : "Светлая тема"}
                  title={lang === "en" ? "Light theme" : "Светлая тема"}
                >
                  <SunIcon style={{ marginRight: 0 }} />
                </button>
                <button
                  className={`theme-btn ${theme === "dark" ? "active" : ""}`}
                  onClick={() => setTheme("dark")}
                  aria-label={lang === "en" ? "Dark theme" : "Тёмная тема"}
                  title={lang === "en" ? "Dark theme" : "Тёмная тема"}
                >
                  <MoonIcon style={{ marginRight: 0 }} />
                </button>
              </div>
            </div>
            <div className="navbar-mobile-quick-actions">
              <button
                className="navbar-mobile-utility-btn navbar-mobile-lang-btn"
                onClick={toggleLanguage}
                aria-label={lang === "en" ? "Switch language" : "Сменить язык"}
                title={lang === "en" ? "Switch language" : "Сменить язык"}
              >
                <GlobeIcon style={{ marginRight: 0 }} />
                <span>{lang.toUpperCase()}</span>
              </button>
              <button
                className="navbar-mobile-utility-btn"
                onClick={toggleThemeMode}
                aria-label={theme === "light"
                  ? (lang === "en" ? "Switch to dark theme" : "Переключить на тёмную тему")
                  : (lang === "en" ? "Switch to light theme" : "Переключить на светлую тему")}
                title={theme === "light"
                  ? (lang === "en" ? "Switch to dark theme" : "Переключить на тёмную тему")
                  : (lang === "en" ? "Switch to light theme" : "Переключить на светлую тему")}
              >
                {theme === "light"
                  ? <SunIcon style={{ marginRight: 0 }} />
                  : <MoonIcon style={{ marginRight: 0 }} />}
              </button>
            </div>
            <div className="navbar-search-mobile">
              <NavbarUserSearch
                lang={lang}
                navigate={navigate}
                currentUsername={user?.username || ""}
                compact
              />
            </div>
          </div>
          <div className="navbar-primary-actions">
            {user ? (
              <>
              <TelegramLinkButton
                user={user}
                token={token}
                onUserUpdate={setUser}
                lang={lang}
                buttonClassName="navbar-desktop-only"
              />
              <div className="navbar-profile navbar-desktop-only" onClick={() => navigate("/profile")}>
                <div className="navbar-avatar">
                  {user.avatar && (user.avatar.startsWith("data:image") || user.avatar.startsWith("http")) ? (
                    <img src={user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                  ) : (
                    user.avatar ? user.avatar : user.username.charAt(0).toUpperCase()
                  )}
                </div>
                <span className="navbar-username">{user.username}</span>
              </div>
              <NotificationBell
                authHeaders={authHeaders}
                lang={lang}
                navigate={navigate}
              />
              <button
                className="navbar-logout-btn icon-btn navbar-desktop-only"
                onClick={handleLogout}
                title={t.logout}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
              <div className="navbar-mobile-overflow" ref={mobileNavMenuRef}>
                <button
                  type="button"
                  className={`navbar-mobile-menu-trigger ${showMobileNavMenu ? "active" : ""}`}
                  onClick={() => setShowMobileNavMenu((prev) => !prev)}
                  aria-label={lang === "en" ? "More actions" : "Ещё действия"}
                  title={lang === "en" ? "More actions" : "Ещё действия"}
                >
                  <ListIcon style={{ marginRight: 0 }} />
                </button>
                {showMobileNavMenu && (
                  <div className="navbar-mobile-menu">
                    <button
                      type="button"
                      className="navbar-mobile-menu-item navbar-mobile-menu-profile"
                      onClick={() => {
                        setShowMobileNavMenu(false);
                        navigate("/profile");
                      }}
                    >
                      <span className="navbar-mobile-menu-avatar">
                        {user.avatar && (user.avatar.startsWith("data:image") || user.avatar.startsWith("http")) ? (
                          <img src={user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover" }} />
                        ) : (
                          user.avatar ? user.avatar : user.username.charAt(0).toUpperCase()
                        )}
                      </span>
                      <span className="navbar-mobile-menu-copy">
                        <strong>{lang === "en" ? "Profile" : "Профиль"}</strong>
                        <span>{user.username}</span>
                      </span>
                    </button>
                    <TelegramLinkButton
                      user={user}
                      token={token}
                      onUserUpdate={setUser}
                      lang={lang}
                      buttonClassName="navbar-mobile-menu-item"
                      onButtonClick={() => setShowMobileNavMenu(false)}
                      menuMode
                    />
                    <button
                      type="button"
                      className="navbar-mobile-menu-item danger"
                      onClick={() => {
                        setShowMobileNavMenu(false);
                        handleLogout();
                      }}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true"
                      >
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                      </svg>
                      <span>{t.logout}</span>
                    </button>
                  </div>
                )}
              </div>
              </>
            ) : (
              <button className="navbar-login-btn" onClick={() => setShowAuth(true)}>{t.login}</button>
            )}
          </div>
        </div>
      </nav>

      {showAuth && (
        <AuthModal
          onClose={() => setShowAuth(false)}
          onAuth={handleAuth}
        />
      )}

      <div className="page-wrapper">
        {/* Profile Page */}
        {page === "profile" ? (
          <Suspense fallback={panelLoader}>
            <ProfilePage user={user} token={token} onLogout={handleLogout} onUpdateUser={setUser} lang={lang} />
          </Suspense>
        ) : (
          <>
            {showChecklistSkeleton ? (
              <ChecklistRouteSkeleton />
            ) : showChecklistErrorState ? (
              <div className="checklist-load-state">
                <div className="checklist-load-card">
                  <div className="checklist-load-title">{lang === "en" ? "Checklist unavailable" : "Не удалось открыть чеклист"}</div>
                  <div className="checklist-load-copy">{error}</div>
                  <button className="action-btn primary" onClick={() => navigate("/")}>
                    {lang === "en" ? "Go home" : "На главную"}
                  </button>
                </div>
              </div>
            ) : showHomeForm && (
              <>
                <div className="hero">
                  <h2>{t.heroTitle}</h2>
                  <p>{t.heroSubtitle}</p>
                </div>

                <div className="form-card">
                  <div className="origin-dest-block">
                    <div className="origin-row">
                      <div className="form-field" style={{ flex: 1 }}>
                        <CitySelect
                          value={originCity}
                          onSelect={(val) => setOriginCity(val)}
                          lang={lang}
                          label={lang === "ru" ? "Откуда" : "From"}
                        />
                      </div>
                    </div>
                    <div className="route-arrow">↓</div>
                  </div>
                  {destinations.map((dest, index) => (
                    <div key={dest.id} className="destination-row">
                      {destinations.length > 1 && (
                        <div className="destination-header">
                          <span className="destination-number">#{index + 1}</span>
                          <button
                            className="remove-dest-btn"
                            onClick={() => handleRemoveDestination(dest.id)}
                            title="Удалить город"
                          >
                            ×
                          </button>
                        </div>
                      )}
                      <div className="form-field">
                        <CitySelect
                          value={dest.city}
                          onSelect={(val) => updateDestination(dest.id, "city", val)}
                          lang={lang}
                        >
                          {/* Per-destination Transport Selection */}
                          <div className="inline-transport-selector" style={{ background: "transparent", border: "none", padding: 0, gap: "2px" }}>
                            {[
                              { id: "plane", icon: <PlaneIcon style={{ marginRight: 0 }} /> },
                              { id: "train", icon: <TrainIcon style={{ marginRight: 0 }} /> },
                              { id: "car", icon: <CarIcon style={{ marginRight: 0 }} /> },
                              { id: "bus", icon: <BusIcon style={{ marginRight: 0 }} /> },
                            ].map(type => (
                              <button
                                key={type.id}
                                className={`transport-btn ${dest.transport === type.id ? "active" : ""}`}
                                onClick={() => updateDestination(dest.id, "transport", type.id)}
                                title={t[type.id] || type.id}
                                style={{ padding: "4px", fontSize: "1.05rem", minWidth: "24px" }}
                              >
                                {type.icon}
                              </button>
                            ))}
                          </div>
                        </CitySelect>
                      </div>

                      <div className="form-field">
                        <DateRangePicker
                          value={dest.dates}
                          onChange={(val) => updateDestination(dest.id, "dates", val)}
                          lang={lang}
                          minDate={index > 0 ? (destinations[index - 1].dates.end ? new Date(destinations[index - 1].dates.end) : new Date()) : new Date()}
                        />
                      </div>

                      {index < destinations.length - 1 && <div className="destination-divider">↓</div>}
                    </div>
                  ))}

                  <div className="form-actions" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                    <button className="add-city-btn" onClick={handleAddDestination} style={{ width: "auto" }}>
                      {t.addCity}
                    </button>

                    {/* Return transport selector */}
                    <div className="return-transport-row" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
                      <label className="section-label" style={{ marginBottom: 0 }}>{t.returnTransport || "Обратно:"}</label>
                      <div className="inline-transport-selector">
                        {[
                          { id: "plane", icon: <PlaneIcon style={{ marginRight: 0 }} /> },
                          { id: "train", icon: <TrainIcon style={{ marginRight: 0 }} /> },
                          { id: "car", icon: <CarIcon style={{ marginRight: 0 }} /> },
                          { id: "bus", icon: <BusIcon style={{ marginRight: 0 }} /> },
                        ].map(type => (
                          <button
                            key={type.id}
                            className={`transport-btn ${returnTransport === type.id ? "active" : ""}`}
                            onClick={() => setReturnTransport(type.id)}
                            title={t[type.id] || type.id}
                          >
                            {type.icon}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="trip-type-selector">
                    <label className="section-label">{lang === "en" ? "Trip Setup" : "Параметры поездки"}</label>
                    <div className="trip-settings-card">
                      <div className="trip-settings-grid trip-settings-quick-grid">
                        <div className="trip-settings-field trip-settings-field-full">
                          <label className="section-label">
                            {lang === "en" ? "Describe the trip for AI" : "Опишите поездку для ИИ"}
                          </label>
                          <textarea
                            className="trip-settings-note-input"
                            value={options.trip_note}
                            onChange={(event) => {
                              updateTripOption("trip_note", event.target.value);
                              resizeTextareaToContent(event.currentTarget);
                            }}
                            placeholder={t.tripNotePlaceholder}
                            rows={1}
                          />
                        </div>

                        <div className="trip-settings-field trip-settings-panel-field trip-settings-panel-field-wide">
                          <div className="trip-settings-panel home-setup-card trip-party-card">
                            <div className="home-setup-card-head">
                              <div className="home-setup-card-copy">
                                <span className="home-setup-card-title">
                                  {lang === "en" ? "Who is traveling" : "Кто едет"}
                                </span>
                              </div>
                            </div>
                            <TripPartyEditor
                              value={options}
                              onChange={updateTripPartyOptions}
                              lang={lang}
                              className="trip-party-editor-card"
                            />
                          </div>
                        </div>

                        {user && (
                          <div className="trip-settings-field trip-settings-panel-field trip-settings-panel-field-half">
                            <div className="trip-settings-panel home-setup-card packing-profile-summary-card">
                              <div className="home-setup-card-head">
                                <div className="home-setup-card-copy">
                                  <span className="home-setup-card-title">
                                    {lang === "en" ? "Base items" : "Базовые вещи"}
                                  </span>
                                </div>
                              </div>
                              <div className="packing-base-items-editor compact">
                                <div className="packing-base-items-input-row compact">
                                  <input
                                    type="text"
                                    className="packing-base-items-input compact"
                                    value={newBaseItem}
                                    onChange={(e) => setNewBaseItem(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === "Enter") {
                                        e.preventDefault();
                                        handleAddBaseItem();
                                      }
                                    }}
                                    placeholder={lang === "en" ? "For example: contact lenses" : "Например: линзы"}
                                  />
                                  <button type="button" className="packing-base-items-add compact" onClick={handleAddBaseItem}>
                                    +
                                  </button>
                                  <button
                                    type="button"
                                    className="compact-list-toggle"
                                    onClick={() => setShowBaseItemsModal(true)}
                                    title={lang === "en" ? "Base items list" : "Список базовых вещей"}
                                  >
                                    <span className="compact-list-toggle-icon" aria-hidden="true">≡</span>
                                    <span>{packingProfile.always_include_items.length}</span>
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}

                        {user && (
                          <div className="trip-settings-field trip-settings-panel-field trip-settings-panel-field-half">
                            <div className="trip-settings-panel collaborator-picker-panel home-setup-card">
                              <div className="home-setup-card-head">
                                <div className="home-setup-card-copy">
                                  <span className="home-setup-card-title">
                                    {lang === "en" ? "Collaborative checklist" : "Совместный чеклист"}
                                  </span>
                                </div>
                              </div>
                              <div className="collaborator-search-row">
                                <div className="collaborator-search-shell">
                                  <input
                                    type="text"
                                    className="collaborator-search-input"
                                    value={collaboratorQuery}
                                    onChange={(e) => setCollaboratorQuery(e.target.value)}
                                    placeholder={lang === "en" ? "Enter username" : "Введите имя пользователя"}
                                  />
                                  {collaboratorResults.length > 0 && (
                                    <div className="collaborator-search-results">
                                      {collaboratorResults.map((person) => (
                                        <button
                                          key={person.id}
                                          type="button"
                                          className="collaborator-search-item"
                                          onClick={() => addCollaborator(person)}
                                        >
                                          <span className="collaborator-search-avatar">
                                            {person.avatar ? (
                                              <img src={person.avatar} alt={person.username} />
                                            ) : (
                                              person.username.charAt(0).toUpperCase()
                                            )}
                                          </span>
                                          <span className="collaborator-search-copy">
                                            <strong>{person.username}</strong>
                                            {person.bio && <span>{person.bio}</span>}
                                          </span>
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                <button
                                  type="button"
                                  className="compact-list-toggle"
                                  onClick={() => setShowCollaboratorsModal(true)}
                                  title={lang === "en" ? "Selected users" : "Список выбранных"}
                                >
                                  <span className="compact-list-toggle-icon" aria-hidden="true">≡</span>
                                  <span>{selectedCollaborators.length}</span>
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="advanced-trip-settings">
                        <button
                          type="button"
                          className={`advanced-trip-settings-toggle ${showAdvancedTripSettings ? "open" : ""}`}
                          onClick={() => setShowAdvancedTripSettings((prev) => !prev)}
                        >
                          <span>
                            {lang === "en" ? "Advanced settings" : "Расширенные настройки"}
                          </span>
                          <span className="advanced-trip-settings-status">
                            {showAdvancedTripSettings
                              ? (lang === "en" ? "Active" : "Активны")
                              : (lang === "en" ? "Off" : "Неактивны")}
                          </span>
                          <span className="advanced-trip-settings-chevron">⌄</span>
                        </button>

                        {showAdvancedTripSettings && (
                          <div className="trip-settings-grid trip-settings-advanced-grid">
                            <TripSettingsDropdown
                              label={lang === "en" ? "Trip scenarios" : "Сценарии поездки"}
                              options={tripActivityOptions}
                              value={options.trip_activities}
                              onChange={toggleTripActivity}
                              multiple
                              summary={tripActivitiesSummary}
                              placeholderActive={selectedTripActivityLabels.length === 0}
                            />

                            <TripSettingsDropdown
                              label={lang === "en" ? "Baggage format" : "Формат багажа"}
                              options={baggageFormatOptions}
                              value={options.baggage_format}
                              onChange={(nextValue) => updateTripOption("baggage_format", nextValue)}
                              placeholder={lang === "en" ? "Select baggage format" : "Выберите формат багажа"}
                            />

                            <TripSettingsDropdown
                              label={t.accommodationLabel}
                              options={accommodationOptions}
                              value={options.accommodation_type}
                              onChange={(nextValue) => updateTripOption("accommodation_type", nextValue)}
                              placeholder={lang === "en" ? "Select accommodation" : "Выберите жильё"}
                            />

                            <TripSettingsDropdown
                              label={t.laundryLabel}
                              options={laundryOptions}
                              value={options.laundry_access}
                              onChange={(nextValue) => updateTripOption("laundry_access", nextValue)}
                              placeholder={lang === "en" ? "Select laundry access" : "Выберите доступ к стирке"}
                            />

                            <TripSettingsDropdown
                              label={t.packingStyleLabel}
                              options={packingStyleOptions}
                              value={options.packing_style}
                              onChange={(nextValue) => updateTripOption("packing_style", nextValue)}
                              placeholder={lang === "en" ? "Select packing style" : "Выберите стиль сборов"}
                            />

                            <TripSettingsDropdown
                              label={lang === "en" ? "Extra factors" : "Дополнительные факторы"}
                              options={packingFactorOptions}
                              value={packingFactorOptions.filter((item) => Boolean(packingProfile[item.id])).map((item) => item.id)}
                              onChange={togglePackingFactor}
                              multiple
                              summary={packingFactorsSummary}
                              placeholderActive={selectedPackingFactorLabels.length === 0}
                            />

                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="form-field generate-field">
                    <button
                      className="generate-btn"
                      onClick={handleSubmit}
                      disabled={false}
                    >
                      {t.generate}
                    </button>
                  </div>
                </div>
              </>
            )}

            {error && !showChecklistErrorState && <div className="error-message">{error}</div>}

            {result && (
              <div className="results-section">
                <h2 className="checklist-header">
                  <div className="checklist-title-group">
                    <span className="checklist-city-name">{translatePlaceLabel(result.city, lang)}</span>
                    <span className="checklist-dates">
                      {renderChecklistHeaderDate(result.start_date || destinations[0]?.dates?.start, lang)}
                      {" — "}
                      {renderChecklistHeaderDate(result.end_date || destinations[destinations.length - 1]?.dates?.end, lang)}
                    </span>
                  </div>
                  {result.user_id === user?.id && (
                    <button
	                      className="invite-action-btn"
                        disabled={isOffline}
	                      onClick={async () => {
	                        setInviteBusyIds([]);
	                        setShowInviteModal(true);
                        if (user?.username) {
                          fetch(`${API_URL}/users/${user.username}/followers`, { headers: authHeaders })
                            .then(r => r.ok ? r.json() : [])
                            .then(data => setFollowers(data))
                            .catch(e => console.error(e));
                        }
                        if (!result.invite_token) {
                          const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/invite-token`, {
                            method: "POST",
                            headers: authHeaders
                          });
                          if (res.ok) {
                            const data = await res.json();
                            setInviteToken(data.invite_token);
                          }
                        } else {
                          setInviteToken(result.invite_token);
                        }
                      }}
                    >{`+ ${lang === "en" ? "Invite" : "Пригласить"}`}</button>
                  )}
                </h2>

                {checklistSyncBadge && (
                  <div className={`checklist-sync-badge ${checklistSyncBadge.tone}`}>
                    {checklistSyncBadge.text}
                  </div>
                )}

                {(savedSlug || id) && (result.user_id === user?.id || (result.backpacks && result.backpacks.length > 0)) && (
                  <div className="baggage-panel">
                    <div className="baggage-panel-primary">
                      {baggageParticipants.length > 0 && (
                        <div className="participant-switcher">
                          {baggageParticipants.map((participant) => (
                            <button
                              key={participant.userId}
                              className={`participant-chip ${activeParticipantId === participant.userId ? "selected" : ""} ${activeTab !== "shared" && activeParticipantId === participant.userId ? "active" : ""}`}
                              onClick={() => selectParticipant(participant.userId)}
                            >
                              <span className="participant-chip-avatar">
                                {participant.isChild ? getInitial(participant.username) : getInitial(participant.isCurrentUser ? (lang === "en" ? "Me" : "Я") : participant.username)}
                              </span>
                              <span className="participant-chip-body">
                                <span className="participant-chip-name">
                                  {participant.isChild ? participant.username : participant.isCurrentUser ? (lang === "en" ? "Me" : "Я") : participant.username}
                                </span>
                                <span className="participant-chip-meta">
                                  {formatBaggageSummary(participant.baggage.length, getParticipantVisibleItemCount(participant), lang)}
                                </span>
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {activeParticipant && (
                      <div className="baggage-panel-secondary">
                        <div className="baggage-panel-header">
                          <div>
                            <div className="baggage-panel-title">
                              {activeParticipant.isChild
                                ? (lang === "en" ? `Child's baggage: ${activeParticipant.username}` : `Багаж ребенка: ${activeParticipant.username}`)
                                : activeParticipant.isCurrentUser ? (lang === "en" ? "My baggage" : "Мой багаж") : (lang === "en" ? `${activeParticipant.username}'s baggage` : `Багаж ${activeParticipant.username}`)}
                            </div>
                            <div className="baggage-panel-subtitle">
                              {formatBaggageSummary(activeParticipant.baggage.length, getParticipantVisibleItemCount(activeParticipant), lang)}
                            </div>
                          </div>
                          <div className="baggage-panel-actions">
                            {canManageSelectedParticipant && activeParticipant.baggage.length > 0 && !showBaggageCreator && (
                              <button
                                className="baggage-create-btn secondary"
                                onClick={() => openBaggageAccess(activeParticipant)}
                                disabled={baggageBusy || isOffline}
                              >
                                {lang === "en" ? "Access" : "Доступ"}
                              </button>
                            )}
                            {canManageSelectedParticipant && !showBaggageCreator && (
                              <button
                                className="baggage-create-btn"
                                onClick={() => setShowBaggageCreator(true)}
                                disabled={baggageBusy || isOffline}
                              >
                                {lang === "en" ? "+ Baggage" : "+ Багаж"}
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="baggage-chip-row">
                          {activeParticipant.baggage.length > 0 ? activeParticipant.baggage.map((bp) => (
                            <div
                              key={bp.id}
                              className={`baggage-chip ${activeTab === bp.id.toString() ? "active" : ""}`}
                              onClick={() => setActiveTab(bp.id.toString())}
                            >
                              <div className="baggage-chip-main">
                                <BackpackIcon style={{ marginRight: "6px" }} />
                                <div className="baggage-chip-copy">
                                  <div className="baggage-chip-heading">
                                    {renamingBaggageId === bp.id ? (
                                      <div
                                        className="baggage-rename-row"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <input
                                          className="baggage-rename-input"
                                          value={renamingBaggageName}
                                          onChange={(e) => setRenamingBaggageName(e.target.value)}
                                          onKeyDown={(e) => {
                                            if (e.key === "Enter") handleRenameBaggage(bp);
                                            if (e.key === "Escape") {
                                              setRenamingBaggageId(null);
                                              setRenamingBaggageName("");
                                            }
                                          }}
                                          autoFocus
                                        />
                                        <button
                                          type="button"
                                          className="baggage-rename-btn save"
                                          onClick={() => handleRenameBaggage(bp)}
                                          disabled={baggageBusy || !renamingBaggageName.trim()}
                                        >
                                          OK
                                        </button>
                                        <button
                                          type="button"
                                          className="baggage-rename-btn"
                                          onClick={() => {
                                            setRenamingBaggageId(null);
                                            setRenamingBaggageName("");
                                          }}
                                          disabled={baggageBusy}
                                        >
                                          ×
                                        </button>
                                      </div>
                                    ) : (
                                      <>
                                        <span className="baggage-chip-name">{translateKnownBaggageName(bp.name || getBaggageKindLabel(bp, lang), lang)}</span>
                                        {bp.is_default && <span className="baggage-chip-badge">{lang === "en" ? "primary" : "основной"}</span>}
                                {canUserEditBaggage(bp, user?.id, result?.backpacks || [], result) && (
                                          <button
                                            type="button"
                                            className="baggage-rename-trigger"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              startRenameBaggage(bp);
                                            }}
                                            title={lang === "en" ? "Rename baggage" : "Переименовать багаж"}
                                            disabled={isOffline}
                                          >
                                            ✎
                                          </button>
                                        )}
                                      </>
                                    )}
                                  </div>
                                  <span className="baggage-chip-meta">
                                    {getBaggageMetaLine(bp, lang)}
                                  </span>
                                </div>
                              </div>
                              <div className="baggage-chip-actions">
                                {canUserEditBaggage(bp, user?.id, result?.backpacks || [], result) && (
                                  <button
                                    className={`baggage-default-toggle ${bp.is_default ? "active" : ""}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleSetDefaultBaggage(bp);
                                    }}
                                    title={bp.is_default ? (lang === "en" ? "Primary baggage" : "Основной багаж") : (lang === "en" ? "Make primary" : "Сделать основным")}
                                    disabled={baggageBusy || bp.is_default || isOffline}
                                  >
                                    <span className="baggage-default-toggle-dot" />
                                  </button>
                                )}
                                {canUserEditBaggage(bp, user?.id, result?.backpacks || [], result) && (
                                  <button
                                    className={`baggage-chip-action ${result.hidden_sections?.includes(`backpack:${bp.id}`) ? "hidden" : "visible"}`}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleToggleSectionVisibility(`backpack:${bp.id}`);
                                    }}
                                    title={result.hidden_sections?.includes(`backpack:${bp.id}`) ? (lang === "en" ? "Hidden from others" : "Скрыто от других") : (lang === "en" ? "Visible to everyone" : "Видно всем")}
                                    disabled={isOffline}
                                  >
                                    {result.hidden_sections?.includes(`backpack:${bp.id}`) ? <LockIcon style={{ marginRight: 0 }} /> : <UnlockIcon style={{ marginRight: 0 }} />}
                                  </button>
                                )}
                                {canUserEditBaggage(bp, user?.id, result?.backpacks || [], result) && !bp.is_default && (
                                  <button
                                    className="baggage-chip-delete"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteBaggage(bp);
                                    }}
                                    title={lang === "en" ? "Delete baggage" : "Удалить багаж"}
                                    disabled={baggageBusy || isOffline}
                                  >
                                    ×
                                  </button>
                                )}
                              </div>
                            </div>
                          )) : (
                            <div className="baggage-empty-hint">
                              {lang === "en" ? "This participant does not have separate baggage yet." : "У этого участника пока нет отдельного багажа."}
                            </div>
                          )}
                        </div>

                        {canManageSelectedParticipant && showBaggageCreator && (
                          <div className="baggage-creator">
                            <div className="baggage-creator-presets">
                              {[
                                lang === "en" ? "Suitcase" : "Чемодан",
                                lang === "en" ? "Carry-on" : "Ручная кладь",
                                lang === "en" ? "Backpack" : "Рюкзак",
                                lang === "en" ? "Hiking backpack" : "Походный рюкзак",
                              ].map((preset) => (
                                <button
                                  key={preset}
                                  className={`baggage-preset-chip ${newBaggageName === preset ? "active" : ""}`}
                                  onClick={() => setNewBaggageName(preset)}
                                  type="button"
                                >
                                  {preset}
                                </button>
                              ))}
                            </div>
                            <div className="baggage-creator-row">
                              <input
                                className="baggage-name-input"
                                type="text"
                                value={newBaggageName}
                                onChange={(e) => setNewBaggageName(e.target.value)}
                                placeholder={lang === "en" ? "For example: Suitcase" : "Например: Чемодан"}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    handleCreateBaggage();
                                  }
                                }}
                                autoFocus
                              />
                              <button
                                className="baggage-confirm-btn"
                                onClick={handleCreateBaggage}
                                disabled={baggageBusy || !newBaggageName.trim()}
                              >
                                {lang === "en" ? "Create" : "Создать"}
                              </button>
                              <button
                                className="baggage-cancel-btn"
                                onClick={() => {
                                  setShowBaggageCreator(false);
                                  setNewBaggageName("");
                                }}
                                disabled={baggageBusy}
                              >
                                {lang === "en" ? "Cancel" : "Отмена"}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}



                <div className="checklist-card">
                  {(() => {
                    const isSharedHidden = !isChecklistParticipant && result.hidden_sections?.includes('shared');
                    const isBackpacksHidden = result.hidden_sections?.includes('backpacks');

                    if (activeTab === 'shared' && isSharedHidden) {
                      return <div className="section-restricted-msg"><LockIcon /> {lang === "en" ? `${result.user?.username || "Owner"} restricted access to this section` : `${result.user?.username || "Владелец"} ограничил просмотр этого раздела`}</div>;
                    }
                    if (activeTab !== 'shared') {
                      const bp = result.backpacks?.find((entry) => entry.id.toString() === activeTab);
                      const isThisBpIsHidden = result.hidden_sections?.includes(`backpack:${activeTab}`);
                      const canViewThisBaggage = Boolean(
                        !bp
                          || !isThisBpIsHidden
                          || bp.user_id === user?.id
                      );
                      if ((isBackpacksHidden && result.user_id !== user?.id) || !canViewThisBaggage) {
                        return <div className="section-restricted-msg"><LockIcon /> {lang === "en" ? `${bp?.user?.username || result.user?.username || "Owner"} restricted access to this baggage` : `${bp?.user?.username || result.user?.username || "Владелец"} ограничил просмотр этого багажа`}</div>;
                      }
                    }

                    let targetItems = result.items || [];
                    let targetRemoved = removedItems;
                    let targetChecked = checkedItems;
                    let targetQuantities = normalizeQuantityMap(result.item_quantities || {});
                    let targetPackedQuantities = normalizePackedQuantityMap(result.packed_quantities || {});
                    let targetItemCategories = normalizeItemCategoryMap(result.item_categories || {});

                    if (activeTab !== "shared" && result.backpacks) {
                      const bp = result.backpacks.find(b => b.id.toString() === activeTab);
                      if (bp) {
                        targetItems = bp.items || [];
                        targetRemoved = bp.removed_items || [];
                        targetChecked = buildCheckedItemsMap(
                          bp.items || [],
                          bp.checked_items || [],
                          bp.item_quantities || {},
                          bp.packed_quantities || {}
                        );
                        targetQuantities = normalizeQuantityMap(bp.item_quantities || {});
                        targetPackedQuantities = normalizePackedQuantityMap(bp.packed_quantities || {});
                        targetItemCategories = normalizeItemCategoryMap(bp.item_categories || {});
                      }
                    }

                    let items = targetItems.filter(item => !targetRemoved.includes(item));

                    if (activeTab === "shared" && result.backpacks) {
                      // Filter out items that are currently in any backpack
                      const allBackpackItems = new Set();
                      result.backpacks.forEach(bp => {
                        if (bp.items) bp.items.forEach(i => allBackpackItems.add(i));
                      });
                      items = items.filter(item => !allBackpackItems.has(item));
                    }

                    const categorySections = buildChecklistCategorySections(items, targetItemCategories, lang);
                    const checklistColumnCount = viewportWidth <= 600 ? 1 : viewportWidth <= 900 ? 2 : 3;
                    const categoryColumns = buildChecklistColumns(categorySections, checklistColumnCount);
                    return (
                      <div className="checklist-multicolumn">
                        {items.length === 0 && <div className="empty-state" style={{ padding: "20px", color: "#888" }}>{lang === "en" ? "The list is empty." : "Список пуст."}</div>}
                        {items.length > 0 && categoryColumns.map((column, columnIndex) => (
                          <div className="checklist-column" key={`checklist-column-${columnIndex}`}>
                            {column.map((section) => (
                              <div className="checklist-category checklist-category-group" key={section.key || section.category}>
                                {!section.isContinuation && <div className="checklist-category-title">{section.category}</div>}
                                <div className="checklist">
                                  {section.items.map((item) => (
                                (() => {
                                  const quantity = getItemQuantity(targetQuantities, item);
                                  const packedQuantity = getPackedQuantity(targetPackedQuantities, item);
                                  const packedState = `${packedQuantity}/${quantity}`;
                                  const canMoveItem = !isOffline && (activeTab === "shared"
                                    ? result?.backpacks?.length > 0
                                    : result?.backpacks?.length > 1);
                                  return (
                                <label
                                  key={item}
                                  className={`checklist-label${targetChecked[item] ? " checked" : ""}${quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab ? " quantity-editor-open" : ""}`}
                                >
                                  <input
                                    type="checkbox"
                                    className="checklist-checkbox"
                                    checked={targetChecked[item] || false}
                                    onChange={() => handleCheck(item)}
                                    disabled={!canMutateCurrentSection}
                                  />
                                    <span className="checklist-item-copy">
                                    <span className="checklist-item-text">{translateChecklistItemLabel(item, lang, activeTab === "shared" ? result?.item_translations || {} : (result?.backpacks?.find((entry) => entry.id.toString() === activeTab)?.item_translations || {}))}</span>
                                    {isMobileChecklistView && (
                                      <span className={`checklist-item-meta${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}>
                                        {packedState}
                                      </span>
                                    )}
                                  </span>
                                  <span className="item-right-controls">
                                    {!isMobileChecklistView && (
                                      canMutateCurrentSection ? (
                                        <button
                                          type="button"
                                          className={`item-progress-badge item-progress-trigger${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}
                                          onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            toggleQuantityEditor(item, quantity, packedQuantity);
                                          }}
                                        >
                                          {packedState}
                                        </button>
                                      ) : (
                                        <span className={`item-progress-badge${packedQuantity >= quantity ? " complete" : packedQuantity > 0 ? " partial" : ""}`}>
                                          {packedState}
                                        </span>
                                      )
                                    )}
                                    {canMutateCurrentSection && (
                                      isMobileChecklistView ? (
                                        <span className="mobile-item-menu-wrap">
                                          <button
                                            type="button"
                                            className="mobile-item-stepper-btn"
                                            title={lang === "en" ? "Pack one less" : "Убрать одну"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              handleQuickPackedChange(item, -1);
                                            }}
                                            disabled={packedQuantity <= 0}
                                          >
                                            -1
                                          </button>
                                          <button
                                            type="button"
                                            className="mobile-item-stepper-btn accent"
                                            title={lang === "en" ? "Pack one more" : "Добавить одну"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              handleQuickPackedChange(item, 1);
                                            }}
                                            disabled={packedQuantity >= quantity}
                                          >
                                            +1
                                          </button>
                                          <button
                                            type="button"
                                            className={`mobile-item-menu-trigger${quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab ? " active" : ""}`}
                                            title={lang === "en" ? "Open item settings" : "Открыть настройки вещи"}
                                            onClick={(e) => {
                                              e.preventDefault();
                                              e.stopPropagation();
                                              toggleQuantityEditor(item, quantity, packedQuantity);
                                            }}
                                          >
                                            •••
                                          </button>
                                        </span>
                                      ) : (
                                        <span className="item-action-group">
                                          {canMoveItem && (
                                            <button
                                              className="checklist-action-btn"
                                              title={activeTab === "shared" ? "Разложить по багажу" : "Переложить в другой багаж"}
                                              onClick={e => {
                                                e.preventDefault();
                                                openMoveItemDialog(item, activeTab === "shared" ? null : Number(activeTab));
                                              }}
                                              tabIndex={-1}
                                            >
                                              <BackpackIcon style={{ width: '16px', height: '16px', marginRight: 0 }} />
                                            </button>
                                          )}
                                          <button
                                            className="checklist-remove-btn"
                                            title="Удалить"
                                            onClick={e => { e.preventDefault(); handleRemoveItem(item); }}
                                            tabIndex={-1}
                                          >×</button>
                                        </span>
                                      )
                                    )}
                                  </span>
                                  {!isMobileChecklistView && canMutateCurrentSection && quantityEditor?.item === item && quantityEditor?.sectionKey === activeTab && (
                                    <div
                                      className="quantity-editor-popover"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                      }}
                                      onMouseDown={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                      }}
                                    >
                                      {isMobileChecklistView && <div className="mobile-sheet-handle" />}
                                      <div className="quantity-editor-title">{item}</div>
                                      <div className="quantity-editor-summary">
                                        <div>
                                          <span className="quantity-editor-summary-label">{lang === "en" ? "Packed" : "Собрано"}</span>
                                          <strong>{quantityEditor.packed}/{quantityEditor.needed}</strong>
                                        </div>
                                        <div>
                                          <span className="quantity-editor-summary-label">{lang === "en" ? "Needed" : "Нужно"}</span>
                                          <strong>{quantityEditor.needed}</strong>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-shortcuts">
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut"
                                          onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                                          disabled={quantityEditor.packed <= 0}
                                        >
                                          -1 {lang === "en" ? "packed" : "собрано"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut"
                                          onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                                          disabled={quantityEditor.packed >= quantityEditor.needed}
                                        >
                                          +1 {lang === "en" ? "packed" : "собрано"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-shortcut accent"
                                          onClick={() => updateQuantityEditorDraft("packed", quantityEditor.needed)}
                                          disabled={quantityEditor.packed >= quantityEditor.needed}
                                        >
                                          {lang === "en" ? "Pack all" : "Собрать всё"}
                                        </button>
                                      </div>
                                      <div className="quantity-editor-row">
                                        <span className="quantity-editor-label">Нужно</span>
                                        <div className="item-quantity-control quantity-editor-control">
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("needed", Math.max(1, quantityEditor.needed - 1))}
                                            disabled={quantityEditor.needed <= 1}
                                          >
                                            −
                                          </button>
                                          <input
                                            type="number"
                                            min="1"
                                            className="item-quantity-input"
                                            value={quantityEditor.needed}
                                            onChange={(e) => updateQuantityEditorDraft("needed", e.target.value)}
                                          />
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("needed", quantityEditor.needed + 1)}
                                          >
                                            +
                                          </button>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-row">
                                        <span className="quantity-editor-label">Собрано</span>
                                        <div className="item-quantity-control quantity-editor-control">
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                                            disabled={quantityEditor.packed <= 0}
                                          >
                                            −
                                          </button>
                                          <input
                                            type="number"
                                            min="0"
                                            max={quantityEditor.needed}
                                            className="item-quantity-input"
                                            value={quantityEditor.packed}
                                            onChange={(e) => updateQuantityEditorDraft("packed", e.target.value)}
                                          />
                                          <button
                                            type="button"
                                            className="item-quantity-btn"
                                            onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                                            disabled={quantityEditor.packed >= quantityEditor.needed}
                                          >
                                            +
                                          </button>
                                        </div>
                                      </div>
                                      <div className="quantity-editor-actions">
                                        <button
                                          type="button"
                                          className="quantity-editor-btn danger"
                                          onClick={() => {
                                            handleRemoveItem(item);
                                            setQuantityEditor(null);
                                          }}
                                        >
                                          {lang === "en" ? "Remove" : "Удалить"}
                                        </button>
                                        <button
                                          type="button"
                                          className="quantity-editor-btn"
                                          onClick={applyQuantityEditor}
                                        >
                                          Применить
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </label>
                                  );
                                })()
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    );
            })()}
            {isMobileChecklistView && canMutateCurrentSection && quantityEditor?.sectionKey === activeTab && (
              <div
                className="mobile-quantity-sheet-backdrop"
                onClick={() => setQuantityEditor(null)}
              >
                <section
                  className="mobile-quantity-sheet"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                  }}
                >
                  <div className="mobile-sheet-handle" />
                  <header className="mobile-quantity-sheet-header">
                    <span>{lang === "en" ? "Item settings" : "Настройка вещи"}</span>
                    <h2>{quantityEditor.item}</h2>
                  </header>
                  <div className="mobile-quantity-sheet-grid">
                    <div>
                      <span>{lang === "en" ? "Packed" : "Собрано"}</span>
                      <strong>{quantityEditor.packed}/{quantityEditor.needed}</strong>
                    </div>
                    <div>
                      <span>{lang === "en" ? "Needed" : "Нужно"}</span>
                      <strong>{quantityEditor.needed}</strong>
                    </div>
                  </div>
                  <div className="mobile-quantity-sheet-actions">
                    <button
                      type="button"
                      onClick={() => updateQuantityEditorDraft("packed", Math.max(0, quantityEditor.packed - 1))}
                      disabled={quantityEditor.packed <= 0}
                    >
                      -1 {lang === "en" ? "packed" : "собрано"}
                    </button>
                    <button
                      type="button"
                      onClick={() => updateQuantityEditorDraft("packed", Math.min(quantityEditor.needed, quantityEditor.packed + 1))}
                      disabled={quantityEditor.packed >= quantityEditor.needed}
                    >
                      +1 {lang === "en" ? "packed" : "собрано"}
                    </button>
                    <button
                      type="button"
                      className="accent"
                      onClick={() => updateQuantityEditorDraft("packed", quantityEditor.needed)}
                      disabled={quantityEditor.packed >= quantityEditor.needed}
                    >
                      {lang === "en" ? "Pack all" : "Собрать всё"}
                    </button>
                  </div>
                  <div className="mobile-quantity-row">
                    <span>{lang === "en" ? "Quantity in list" : "Количество в списке"}</span>
                    <div>
                      <button
                        type="button"
                        onClick={() => updateQuantityEditorDraft("needed", Math.max(1, quantityEditor.needed - 1))}
                        disabled={quantityEditor.needed <= 1}
                      >
                        -
                      </button>
                      <strong>{quantityEditor.needed}</strong>
                      <button
                        type="button"
                        onClick={() => updateQuantityEditorDraft("needed", quantityEditor.needed + 1)}
                      >
                        +
                      </button>
                    </div>
                  </div>
                  <div className="mobile-quantity-sheet-secondary">
                    {canMoveQuantityEditorItem && (
                      <button
                        type="button"
                        onClick={() => {
                          const sourceBackpackId = quantityEditor.sectionKey === "shared"
                            ? null
                            : Number(quantityEditor.sectionKey);
                          setQuantityEditor(null);
                          openMoveItemDialog(quantityEditor.item, sourceBackpackId);
                        }}
                      >
                        {quantityEditor.sectionKey === "shared"
                          ? (lang === "en" ? "Sort into baggage" : "Разложить")
                          : (lang === "en" ? "Move item" : "Переложить")}
                      </button>
                    )}
                    <button
                      type="button"
                      className="danger"
                      onClick={() => {
                        handleRemoveItem(quantityEditor.item);
                        setQuantityEditor(null);
                      }}
                    >
                      {lang === "en" ? "Remove" : "Удалить"}
                    </button>
                  </div>
                  <div className="mobile-quantity-sheet-footer">
                    <button
                      type="button"
                      className="quantity-editor-btn subtle"
                      onClick={() => setQuantityEditor(null)}
                    >
                      {lang === "en" ? "Close" : "Закрыть"}
                    </button>
                    <button
                      type="button"
                      className="quantity-editor-btn"
                      onClick={applyQuantityEditor}
                    >
                      {lang === "en" ? "Apply" : "Применить"}
                    </button>
                  </div>
                </section>
              </div>
            )}

                  <div className="checklist-actions">
                    {canMutateCurrentSection && (
                      <>
                        <button className="action-btn" onClick={resetChecklist}>{t.reset}</button>
                        <button className="action-btn" onClick={toggleAddItemMode}>
                          {addItemMode ? t.cancel : t.addItem}
                        </button>
                        {addItemMode && (
                          <div className="add-item-form">
                            <input
                              className="add-item-input"
                              type="text"
                              value={newItem}
                              onChange={e => setNewItem(e.target.value)}
                              placeholder={t.newItem}
                              onKeyDown={e => { if (e.key === "Enter") handleAddItem(); }}
                              autoFocus
                            />
                            <select
                              className="add-item-select"
                              value={newItemCategory}
                              onChange={(e) => setNewItemCategory(e.target.value)}
                            >
                              <option value="">{lang === "en" ? "Auto category" : "Автокатегория"}</option>
                              {(CHECKLIST_CATEGORY_OPTIONS[lang] || CHECKLIST_CATEGORY_OPTIONS.ru).map((category) => (
                                <option key={category} value={category}>{category}</option>
                              ))}
                            </select>
                            <input
                              className="add-item-quantity-input"
                              type="number"
                              min="1"
                              value={newItemQuantity}
                              onChange={(e) => setNewItemQuantity(Math.max(1, Number(e.target.value) || 1))}
                              onKeyDown={e => { if (e.key === "Enter") handleAddItem(); }}
                            />
                            <button className="action-btn primary" onClick={handleAddItem}>OK</button>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>

                {/* Weather Forecast */}
                {result.daily_forecast && result.daily_forecast.length > 0 && (
                  <div className={`forecast-section ${!showForecast ? 'collapsed' : ''}`}>
                    <div className="forecast-header" onClick={() => setShowForecast(!showForecast)}>
                      <h3><span style={{ display: 'flex', alignItems: 'center' }}><WeatherIcon /> {t.forecast}</span></h3>
                      <button className="collapse-toggle">
                        <span className={`chevron ${showForecast ? 'up' : ''}`}>▾</span>
                      </button>
                    </div>

                    {showForecast && (
                      <div className="forecast-content">
                        {Object.entries(
                          result.daily_forecast.reduce((acc, day) => {
                            const cityName = day.city || result.city || "";
                            if (!acc[cityName]) acc[cityName] = [];
                            acc[cityName].push(day);
                            return acc;
                          }, {})
                        ).map(([cityName, days]) => {
                          const forecastRows = viewportWidth >= 1024 ? splitForecastDays(days) : [days];
                          return (
                            <div key={cityName} className="city-forecast-group">
                              {Object.keys(result.daily_forecast.reduce((acc, day) => {
                                const name = day.city || result.city || "";
                                acc[name] = true;
                                return acc;
                              }, {})).length > 1 && (
                                  <h4 className="city-forecast-title">📍 {cityName}</h4>
                                )}
                              <div className={`forecast-grid forecast-grid-count-${days.length}`}>
                                {forecastRows.map((row, rowIndex) => (
                                  <div
                                    key={`${cityName}-${rowIndex}`}
                                    className="forecast-grid-row"
                                    style={viewportWidth >= 1024 ? { "--forecast-grid-row-width": `${getForecastRowWidth(row.length)}px` } : undefined}
                                  >
                                    {row.map((day) => (
                                      <div key={day.date} className={`forecast-card${day.source === "historical" ? " forecast-historical" : ""}`}>
                                        <div className="forecast-date">{formatDate(day.date)}</div>

                                        <img
                                          src={`https://openweathermap.org/img/wn/${day.icon}@2x.png`}
                                          alt={translateWeatherConditionLabel(day.condition, lang)}
                                          className="forecast-icon"
                                        />
                                        <div className="forecast-conditions">{translateWeatherConditionLabel(day.condition, lang)}</div>
                                        <div className="forecast-temp">
                                          {day.temp_min.toFixed(1)}° / {day.temp_max.toFixed(1)}°C
                                        </div>
                                        <div className="forecast-details">
                                          {day.humidity != null && <span title={t.humidity} style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}><DropletIcon style={{ width: '14px', height: '14px', marginRight: '3px' }} /> {day.humidity}%</span>}
                                          {day.wind_speed != null && <span title={t.wind} style={{ display: 'inline-flex', alignItems: 'center', whiteSpace: 'nowrap' }}><WindIcon style={{ width: '14px', height: '14px', marginRight: '3px' }} /> {day.wind_speed.toFixed(0)} {t.kmh}</span>}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Route Timeline (multi-city) */}
                {destinations.length > 1 && result && (
                  <div className="route-timeline">
                    <h3 className="section-title">🗺 {t.routeTitle || "Маршрут"}</h3>
                    <div className="timeline-track">
                      {destinations.map((dest, i) => (
                        <div key={i} className="timeline-stop">
                          <div className="timeline-dot" />
                          {i < destinations.length - 1 && <div className="timeline-line" />}
                          <div className="timeline-info">
                            <div className="timeline-city">{typeof dest.city === "object" ? (dest.city?.name || dest.city?.fullName || "...") : (dest.city || "...")}</div>
                            {dest.dates?.start && (
                              <div className="timeline-dates">
                                {new Date(dest.dates.start).toLocaleDateString(formatChecklistLocale(lang), { day: "numeric", month: "short" })}
                                {" — "}
                                {new Date(dest.dates.end).toLocaleDateString(formatChecklistLocale(lang), { day: "numeric", month: "short" })}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Itinerary Section */}
                {result && result.start_date && result.end_date && savedSlug && (
                  <div className="itinerary-wrapper">
                    {!isChecklistParticipant && result.hidden_sections?.includes('itinerary') ? (
                      <div className="section-restricted-msg" style={{ background: 'var(--bg-secondary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><LockIcon /> {lang === "en" ? `${result.user?.username || "Owner"} restricted access to the itinerary` : `${result.user?.username || "Владелец"} ограничил просмотр плана поездки`}</div>
                      </div>
                    ) : (
                      <ItinerarySection
                        checklist={result}
                        lang={lang}
                        slug={savedSlug}
                        isOwner={!!isChecklistParticipant}
                        realOwnerId={result.user_id}
                        currentUserId={user?.id}
                        hiddenSections={result.hidden_sections}
                        onToggleVisibility={handleToggleSectionVisibility}
                        requestConfirm={requestConfirm}
                        highlightedEventIds={highlightedItineraryEventIds}
                      />
                    )}
                  </div>
                )}

                {result && !(!isChecklistParticipant && result.hidden_sections?.includes('itinerary')) && (
                  <TripMapSection
                    checklist={result}
                    lang={lang}
                    compact={isMobileChecklistView}
                    highlightedEventIds={highlightedItineraryEventIds}
                    theme={theme}
                  />
                )}

                {result && savedSlug && (
                  <div className="expenses-wrapper">
                    {!isChecklistParticipant && result.hidden_sections?.includes('expenses') ? (
                      <div className="section-restricted-msg" style={{ background: 'var(--bg-secondary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}><LockIcon /> {lang === "en" ? `${result.user?.username || "Owner"} restricted access to expenses` : `${result.user?.username || "Владелец"} ограничил просмотр трат`}</div>
                      </div>
                    ) : (
                      <ExpensesSection
                        checklist={result}
                        lang={lang}
                        slug={savedSlug}
                        token={token}
                        canEdit={Boolean(isChecklistParticipant && token)}
                        realOwnerId={result.user_id}
                        currentUserId={user?.id}
                        hiddenSections={result.hidden_sections}
                        onToggleVisibility={handleToggleSectionVisibility}
                        onChecklistUpdated={handleChecklistUpdated}
                        requestConfirm={requestConfirm}
                        isOffline={isOffline}
                      />
                    )}
                  </div>
                )}

                {result && (
                  <TripReviewsSection
                    checklist={result}
                    user={user}
                    token={token}
                    lang={lang}
                    canReview={canReviewTrip}
                    onReviewSaved={handleReviewSaved}
                    requestConfirm={requestConfirm}
                  />
                )}

                {/* Attractions */}
                {result?.city && (
                  <AttractionsSection city={result.city} lang={lang} compact={isMobileChecklistView} user={user} token={token} />
                )}

                {/* Flights — only for cities with plane transport */}
                {isChecklistParticipant && (() => {
                  if (!result || !result.city) return null;
                  const allCities = result.city.split(" + ").map(c => c.trim());
                  const transports = result.transports || [];
                  // transports array: [to_city0, to_city1, ..., return_transport]
                  // Last element is the return transport
                  const returnTr = transports.length > allCities.length ? transports[transports.length - 1] : (transports.length > 0 ? "plane" : "plane");
                  // Outbound: filter cities where transport is "plane"
                  const outboundCities = transports.length > 0
                    ? allCities.filter((_, i) => (transports[i] || "plane") === "plane")
                    : allCities;
                  // Return: show if return transport is plane, from the last city
                  const lastCity = allCities[allCities.length - 1];
                  const showReturn = returnTr === "plane";
                  // If no outbound and no return — hide section entirely
                  if (outboundCities.length === 0 && !showReturn) return null;
                  // Build the outbound city string
                  const outboundCity = outboundCities.length > 0 ? outboundCities[0] : null;
                  return (
                    <FlightsSection
                      key={"fl-" + (outboundCity || lastCity)}
                      city={outboundCity || lastCity}
                      startDate={result.start_date || destinations[0]?.dates?.start}
                      returnDate={showReturn ? (result.end_date || destinations[destinations.length - 1]?.dates?.end) : null}
                      returnCity={showReturn ? lastCity : null}
                      origin={originCity?.fullName || originCity || result.origin_city || ""}
                      lang={lang}
                      compact={isMobileChecklistView}
                      tripProfile={result.trip_profile || null}
                    />
                  );
                })()}

                {/* Hotels */}
                {isChecklistParticipant && result && result.city && !result.trip_profile?.accommodation_selected && (
                  <HotelsSection key={"ht-" + result.city} city={result.city} startDate={result.start_date || destinations[0]?.dates?.start} endDate={result.end_date || destinations[destinations.length - 1]?.dates?.end} lang={lang} compact={isMobileChecklistView} tripProfile={result.trip_profile || null} />
                )}

                {/* eSIM */}
                {isChecklistParticipant && result && result.city && (
                  <EsimSection key={"esim-" + result.city} city={result.city} lang={lang} compact={isMobileChecklistView} />
                )}

              </div>
            )}
          </>
        )}
      </div>

      {showPackingModal && (
        <div className="modal-overlay" onClick={() => {
          setPackingProfileDraft(packingProfile);
          setNewBaseItem("");
          setShowPackingModal(false);
        }}>
          <div className="modal-content packing-settings-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => {
              setPackingProfileDraft(packingProfile);
              setNewBaseItem("");
              setShowPackingModal(false);
            }}>&times;</button>
            <h3>{lang === "en" ? "Packing settings" : "Настройки сборов"}</h3>
            <p className="packing-settings-copy">
              {lang === "en"
                ? "These preferences are applied when a new checklist is generated from the home page."
                : "Эти параметры будут использоваться при создании нового чеклиста с главной страницы."}
            </p>

            <div className="packing-settings-group">
              <span className="packing-settings-label">{lang === "en" ? "Extra factors" : "Дополнительные факторы"}</span>
              <div className="packing-settings-toggles">
                {[
                  {
                    key: "traveling_with_pet",
                    label: lang === "en" ? "Traveling with pet" : "Путешествую с питомцем",
                  },
                  {
                    key: "has_allergies",
                    label: lang === "en" ? "There are allergies" : "Есть аллергии",
                  },
                ].map((item) => (
                  <label key={item.key} className={`packing-settings-toggle ${packingProfileDraft[item.key] ? "active" : ""}`}>
                    <input
                      type="checkbox"
                      className="packing-settings-toggle-input"
                      checked={Boolean(packingProfileDraft[item.key])}
                      onChange={(e) => setPackingProfileDraft((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                    />
                    <span className="packing-settings-toggle-box" aria-hidden="true" />
                    <span>{item.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="packing-settings-group">
              <span className="packing-settings-label">{lang === "en" ? "Always add" : "Всегда добавлять"}</span>
              <div className="packing-base-items-editor">
                <div className="packing-base-items-input-row">
                  <input
                    type="text"
                    className="packing-base-items-input"
                    value={newBaseItem}
                    onChange={(e) => setNewBaseItem(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddBaseItem();
                      }
                    }}
                    placeholder={lang === "en" ? "For example: contact lenses" : "Например: линзы"}
                  />
                  <button type="button" className="packing-base-items-add" onClick={handleAddBaseItem}>
                    {lang === "en" ? "Add" : "Добавить"}
                  </button>
                </div>
                {packingProfileDraft.always_include_items.length > 0 ? (
                  <div className="packing-base-items-list">
                    {packingProfileDraft.always_include_items.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className="packing-base-item-chip"
                        onClick={() => handleRemoveBaseItem(item)}
                        title={lang === "en" ? "Remove item" : "Убрать вещь"}
                      >
                        <span>{item}</span>
                        <span>×</span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="packing-base-items-empty">
                    {lang === "en" ? "No personal base items yet" : "Пока нет личных базовых вещей"}
                  </div>
                )}
              </div>
            </div>

            <div className="packing-settings-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setPackingProfileDraft(packingProfile);
                  setNewBaseItem("");
                  setShowPackingModal(false);
                }}
                disabled={packingProfileSaving}
              >
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
              <button type="button" className="btn-primary" onClick={handleSavePackingProfile} disabled={packingProfileSaving}>
                {packingProfileSaving ? "..." : (lang === "en" ? "Save" : "Сохранить")}
              </button>
            </div>
          </div>
        </div>
      )}

      {showBaseItemsModal && (
        <div className="modal-overlay" onClick={() => setShowBaseItemsModal(false)}>
          <div className="modal-content base-items-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="modal-close" onClick={() => setShowBaseItemsModal(false)}>&times;</button>
            <h3>{lang === "en" ? "Base items" : "Базовые вещи"}</h3>
            <p className="packing-settings-copy">
              {lang === "en"
                ? "These items will be added to every generated checklist."
                : "Эти вещи будут добавляться в каждый новый чеклист."}
            </p>

            {packingProfile.always_include_items.length > 0 ? (
              <div className="packing-base-items-list modal-list">
                {packingProfile.always_include_items.map((item) => (
                  <button
                    key={item}
                    type="button"
                    className="packing-base-item-chip"
                    onClick={() => handleRemoveBaseItem(item)}
                    title={lang === "en" ? "Remove item" : "Убрать вещь"}
                  >
                    <span>{item}</span>
                    <span>×</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="packing-base-items-empty">
                {lang === "en" ? "No base items yet" : "Пока нет базовых вещей"}
              </div>
            )}
          </div>
        </div>
      )}

      {showCollaboratorsModal && (
        <div className="modal-overlay" onClick={() => setShowCollaboratorsModal(false)}>
          <div className="modal-content base-items-modal collaborators-modal" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="modal-close" onClick={() => setShowCollaboratorsModal(false)}>&times;</button>
            <h3>{lang === "en" ? "Selected users" : "Выбранные пользователи"}</h3>
            <p className="packing-settings-copy">
              {lang === "en"
                ? "These users will be invited to the collaborative checklist."
                : "Эти пользователи будут приглашены в совместный чеклист."}
            </p>

            {selectedCollaborators.length > 0 ? (
              <div className="collaborator-chip-list modal-list">
                {selectedCollaborators.map((person) => (
                  <button
                    key={person.id}
                    type="button"
                    className="collaborator-chip"
                    onClick={() => removeCollaborator(person.id)}
                    title={lang === "en" ? "Remove" : "Убрать"}
                  >
                    <span className="collaborator-chip-avatar">
                      {person.avatar ? (
                        <img src={person.avatar} alt={person.username} />
                      ) : (
                        person.username.charAt(0).toUpperCase()
                      )}
                    </span>
                    <span className="collaborator-chip-name">{person.username}</span>
                    <span className="collaborator-chip-remove">×</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="packing-base-items-empty">
                {lang === "en" ? "No selected users yet" : "Пока нет выбранных пользователей"}
              </div>
            )}
          </div>
        </div>
      )}

      {moveItemDialog && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => !moveItemBusy && setMoveItemDialog(null)}>
          <div className="modal-content baggage-access-modal item-move-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => !moveItemBusy && setMoveItemDialog(null)}>&times;</button>
            <h3>{lang === "en" ? "Move item" : "Переложить вещь"}</h3>
            <p className="invite-modal-desc">
              {lang === "en"
                ? `Choose whether to move "${moveItemDialog.item}" to your baggage or assign it to another participant.`
                : `Выбери, куда переложить «${moveItemDialog.item}»: к себе в другой багаж или другому участнику.`}
            </p>
            <div className="baggage-access-list move-destination-groups">
              {ownMoveDestinations.length > 0 && (
                <div className="move-destination-section">
                  <div className="move-destination-title">
                    {lang === "en" ? "Move to my baggage" : "Переложить к себе"}
                  </div>
                  <div className="move-destination-subtitle">
                    {lang === "en" ? "Another suitcase, backpack or bag of yours." : "В другой свой чемодан, рюкзак или сумку."}
                  </div>
                  <div className="baggage-access-list">
                    {ownMoveDestinations.map((destination) => (
                      <button
                        key={destination.id}
                        type="button"
                        className={`baggage-access-item move-destination-item ${moveItemDialog.targetBackpackId === destination.id ? "active" : ""}`}
                        onClick={() => setMoveItemDialog((prev) => ({ ...prev, targetBackpackId: destination.id }))}
                      >
                        <span className="baggage-access-check" aria-hidden="true" />
                        <span className="baggage-access-avatar">
                          {getInitial(destination.title)}
                        </span>
                        <span className="baggage-access-copy">
                          <strong>{destination.title}</strong>
                          <span>{destination.subtitle}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {otherMoveDestinations.length > 0 && (
                <div className="move-destination-section">
                  <div className="move-destination-title">
                    {lang === "en" ? "Give to another participant" : "Передать другому участнику"}
                  </div>
                  <div className="move-destination-subtitle">
                    {lang === "en" ? "Move the item straight into someone else's baggage." : "Сразу переложить вещь в багаж другого человека."}
                  </div>
                  <div className="baggage-access-list">
                    {otherMoveDestinations.map((destination) => (
                      <button
                        key={destination.id}
                        type="button"
                        className={`baggage-access-item move-destination-item ${moveItemDialog.targetBackpackId === destination.id ? "active" : ""}`}
                        onClick={() => setMoveItemDialog((prev) => ({ ...prev, targetBackpackId: destination.id }))}
                      >
                        <span className="baggage-access-check" aria-hidden="true" />
                        <span className="baggage-access-avatar">
                          {getInitial(destination.title)}
                        </span>
                        <span className="baggage-access-copy">
                          <strong>{destination.title}</strong>
                          <span>{destination.subtitle}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {moveDestinations.length === 0 && (
                <div className="packing-base-items-empty">
                  {lang === "en" ? "There is nowhere to move this item yet." : "Пока некуда переложить эту вещь."}
                </div>
              )}
            </div>
            <div className="baggage-access-actions">
              <button className="action-btn" onClick={() => setMoveItemDialog(null)} disabled={moveItemBusy}>
                {lang === "en" ? "Cancel" : "Отмена"}
              </button>
              <button
                className="action-btn primary"
                onClick={handleConfirmMoveItem}
                disabled={moveItemBusy || !moveItemDialog.targetBackpackId}
              >
                {moveItemBusy ? "..." : (lang === "en" ? "Move" : "Переложить")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно приглашения */}
      {accessOwner && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => setAccessOwner(null)}>
          <div className="modal-content baggage-access-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setAccessOwner(null)}>&times;</button>
            <h3>{lang === "en" ? "Baggage access" : "Доступ к багажу"}</h3>
            <p className="invite-modal-desc">
              {lang === "en"
                ? `Choose who can check off, add, and remove items in the entire "${accessOwner.displayName}" section.`
                : `Выбери, кто сможет отмечать, добавлять и удалять вещи во всем разделе «${accessOwner.displayName}».`}
            </p>
            <div className="baggage-access-list">
              {baggageParticipants
                .filter((participant) => !participant.isChild && participant.userId !== accessOwner.userId)
                .map((participant) => (
                  <label key={participant.userId} className={`baggage-access-item ${accessEditorIds.includes(participant.userId) ? "active" : ""}`}>
                    <input
                      type="checkbox"
                      className="baggage-access-input"
                      checked={accessEditorIds.includes(participant.userId)}
                      onChange={() => handleToggleBaggageEditor(participant.userId)}
                    />
                    <span className="baggage-access-check" aria-hidden="true" />
                    <span className="baggage-access-avatar">
                      {getInitial(participant.isCurrentUser ? (lang === "en" ? "Me" : "Я") : participant.username)}
                    </span>
                    <span className="baggage-access-copy">
                      <strong>{participant.isCurrentUser ? (lang === "en" ? "Me" : "Я") : participant.username}</strong>
                      <span>{formatBaggageCount(participant.baggage.length, lang)}</span>
                    </span>
                  </label>
                ))}
            </div>
            <div className="baggage-access-actions">
              <button className="action-btn" onClick={() => setAccessOwner(null)} disabled={baggageBusy}>{lang === "en" ? "Close" : "Закрыть"}</button>
              <button className="action-btn primary" onClick={handleSaveBaggageAccess} disabled={baggageBusy}>{lang === "en" ? "Save access" : "Сохранить доступ"}</button>
            </div>
          </div>
        </div>
      )}

      {showInviteModal && (
        <div className="modal-overlay modal-overlay-lifted" onClick={() => setShowInviteModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowInviteModal(false)}>&times;</button>
            <h3 style={{ marginTop: 0 }}>{lang === "en" ? "🔗 Invite to trip" : "🔗 Пригласить в путешествие"}</h3>

            <p className="invite-modal-desc">{lang === "en" ? "Your followers:" : "Ваши подписчики:"}</p>
            <div className="invite-followers-list">
              {followers.length > 0 ? followers.map(f => {
                const followerId = normalizeUserId(f.id);
                const isAlreadyInChecklist = checklistParticipantIds.has(followerId) || inviteAlreadyIdSet.has(followerId);
                const isInviteBusy = inviteBusyIdSet.has(followerId);
                const isInviteSent = inviteSentIdSet.has(followerId);
                const isInviteDisabled = isAlreadyInChecklist || isInviteBusy || isInviteSent;
                const inviteButtonLabel = isAlreadyInChecklist
                  ? (lang === "en" ? "Already in list" : "Уже в чеклисте")
                  : isInviteSent
                    ? (lang === "en" ? "Sent" : "Отправлено")
                    : isInviteBusy
                      ? (lang === "en" ? "Sending..." : "Отправляем...")
                      : (lang === "en" ? "Invite" : "Пригласить");

                return (
                  <div key={f.id} className="invite-follower-item">
                    <div className="follower-avatar-small">
                      {f.avatar && (f.avatar.startsWith("data:image") || f.avatar.startsWith("http")) ? (
                        <img src={f.avatar} alt="Avatar" />
                      ) : (
                        f.avatar ? f.avatar : f.username.charAt(0).toUpperCase()
                      )}
                    </div>
                    <span className="follower-name">{f.username}</span>
                    <button
                      className="follower-invite-btn"
                      disabled={isInviteDisabled}
	                      onClick={async () => {
	                        if (isInviteDisabled) return;
	                        setInviteBusyIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                        try {
	                          const res = await fetch(`${API_URL}/checklists/${savedSlug || id}/invite/${f.id}`, {
                            method: "POST",
                            headers: authHeaders
	                          });
	                          if (res.status === 409) {
	                            setInviteAlreadyIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                            return;
	                          }
                          if (!res.ok) {
                            const data = await readJsonSafely(res);
                            throw new Error(data?.detail || "Invite failed");
                          }
	                          setInviteSentIds((prev) => (prev.includes(followerId) ? prev : [...prev, followerId]));
	                        } catch (err) {
	                          console.error(err);
	                        } finally {
	                          setInviteBusyIds((prev) => prev.filter((id) => id !== followerId));
	                        }
                      }}
                    >
                      {inviteButtonLabel}
                    </button>
                  </div>
                );
              }) : (
                <div className="empty-subscribers" style={{ textAlign: "center", color: "#666", padding: "20px" }}>У вас пока нет подписчиков</div>
              )}
            </div>

            <p className="invite-modal-desc" style={{ marginTop: "25px" }}>Или отправьте им ссылку для присоединения к чеклисту:</p>
            {inviteToken ? (
              <>
                <div className="invite-link-box">
                  <input
                    type="text"
                    readOnly
                    value={`${window.location.origin}/join/${inviteToken}`}
                    className="invite-input"
                  />
                  <button
                    className="copy-btn action-btn primary"
                    onClick={() => {
                      navigator.clipboard.writeText(`${window.location.origin}/join/${inviteToken}`);
                      alert("Ссылка скопирована!");
                    }}
                  >Копировать</button>
                </div>
                {normalizeTripParty(result?.trip_profile || {}).child_profiles.filter((profile) => !normalizeUserId(profile.linked_user_id)).length > 0 && (
                  <div className="child-invite-links">
                    <p className="invite-modal-desc">Если ребёнок зайдёт сам, отправьте ему персональную ссылку:</p>
                    {normalizeTripParty(result?.trip_profile || {}).child_profiles
                      .filter((profile) => !normalizeUserId(profile.linked_user_id))
                      .map((profile, index) => {
                        const childLink = `${window.location.origin}/join/${inviteToken}?child_profile_id=${encodeURIComponent(profile.id)}`;
                        return (
                          <div key={profile.id} className="child-invite-row">
                            <span>{getChildProfileDisplayName(profile, lang, index)}</span>
                            <button
                              className="copy-btn action-btn"
                              onClick={() => {
                                navigator.clipboard.writeText(childLink);
                                alert("Ссылка скопирована!");
                              }}
                            >
                              Копировать
                            </button>
                          </div>
                        );
                      })}
                  </div>
                )}
              </>
            ) : (
              <div className="loading-spinner" style={{ margin: "20px auto" }}></div>
            )}
          </div>
        </div>
      )}

      {/* AI Assistant Chat Widget */}
      {result && (
        <Suspense fallback={null}>
          <AIChatWidget
            city={result.destinations?.[0]?.city || result.city}
            startDate={result.destinations?.[0]?.start_date || result.start_date}
            endDate={result.destinations?.[result.destinations?.length - 1]?.end_date || result.end_date}
            avgTemp={result.avg_temp}
            tripType={result.trip_type || result.trip_profile?.trip_type || options.trip_type}
            tripProfile={result.trip_profile || null}
            checklistSlug={savedSlug || result.slug}
            token={token}
            onChecklistUpdated={handleChecklistUpdated}
            onPlanApplied={handlePlanApplied}
            language={lang}
            backpacks={result.backpacks || []}
            hiddenSections={result.hidden_sections || []}
            localCurrency={getExpenseLocalCurrency(result)}
            isAdmin={Boolean(user?.is_admin)}
            currentUserId={user?.id}
            events={result.events || []}
          />
        </Suspense>
      )}

      <ConfirmDialog
        open={Boolean(confirmDialog)}
        title={confirmDialog?.title || ""}
        message={confirmDialog?.message || ""}
        confirmLabel={confirmDialog?.confirmLabel || (lang === "en" ? "Confirm" : "Подтвердить")}
        cancelLabel={confirmDialog?.cancelLabel || (lang === "en" ? "Cancel" : "Отмена")}
        tone={confirmDialog?.tone || "default"}
        onConfirm={() => closeConfirmDialog(true)}
        onCancel={() => closeConfirmDialog(false)}
      />
      {appNotice && (
        <div className={`app-notice app-notice-${appNotice.tone}`} role="status" aria-live="polite">
          <div className="app-notice-copy">
            <div className="app-notice-title">{lang === "en" ? "Notice" : "Уведомление"}</div>
            <div className="app-notice-message">{appNotice.message}</div>
          </div>
          <button
            type="button"
            className="app-notice-close"
            onClick={() => setAppNotice(null)}
            aria-label={lang === "en" ? "Close notification" : "Закрыть уведомление"}
          >
            ×
          </button>
        </div>
      )}
    </>
  );
};

export default App;
