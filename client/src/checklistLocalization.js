import { API_URL } from "./appUtils";

const normalizeLookupKey = (value = "") => String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
const ITEM_TRANSLATION_CACHE_KEY = "luggify:itemTranslationCache:v1";
const itemTranslationCache = new Map();

const readItemTranslationCache = () => {
  if (itemTranslationCache.size > 0 || typeof window === "undefined") return itemTranslationCache;
  try {
    const raw = window.localStorage.getItem(ITEM_TRANSLATION_CACHE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    Object.entries(parsed || {}).forEach(([key, value]) => {
      if (value && typeof value === "object") {
        itemTranslationCache.set(key, value);
      }
    });
  } catch {
    // Ignore unavailable localStorage or malformed cached translations.
  }
  return itemTranslationCache;
};

const writeItemTranslationCache = () => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      ITEM_TRANSLATION_CACHE_KEY,
      JSON.stringify(Object.fromEntries(itemTranslationCache.entries()))
    );
  } catch {
    // Ignore localStorage write failures in private/offline modes.
  }
};

const buildLookup = (pairs = []) => {
  const toEn = new Map();
  const toRu = new Map();

  pairs.forEach(([ru, en]) => {
    const ruKey = normalizeLookupKey(ru);
    const enKey = normalizeLookupKey(en);
    if (ruKey && !toEn.has(ruKey)) toEn.set(ruKey, en);
    if (enKey && !toRu.has(enKey)) toRu.set(enKey, ru);
  });

  return { toEn, toRu };
};

const translateKnownValue = (value, lang, lookup) => {
  const original = String(value || "").trim();
  if (!original) return original;
  const normalized = normalizeLookupKey(original);
  if (!normalized) return original;
  return (lang === "en" ? lookup.toEn.get(normalized) : lookup.toRu.get(normalized)) || original;
};

const CATEGORY_PAIRS = [
  ["Важное", "Essentials"],
  ["Документы", "Documents"],
  ["Одежда", "Clothes"],
  ["Гигиена", "Hygiene"],
  ["Техника", "Electronics"],
  ["Аптечка", "Pharmacy"],
  ["Для детей", "Kids"],
  ["Кемпинг", "Camping"],
  ["Прочее", "Misc"],
];

const WEATHER_CONDITION_PAIRS = [
  ["Ясно", "Clear sky"],
  ["Преимущественно ясно", "Mainly clear"],
  ["Переменная облачность", "Partly cloudy"],
  ["Пасмурно", "Overcast"],
  ["Туман", "Fog"],
  ["Изморозь", "Depositing rime fog"],
  ["Легкая морось", "Light drizzle"],
  ["Лёгкая морось", "Light drizzle"],
  ["Умеренная морось", "Moderate drizzle"],
  ["Сильная морось", "Dense drizzle"],
  ["Небольшой дождь", "Slight rain"],
  ["Умеренный дождь", "Moderate rain"],
  ["Сильный дождь", "Heavy rain"],
  ["Ледяной дождь", "Freezing rain"],
  ["Сильный ледяной дождь", "Heavy freezing rain"],
  ["Небольшой снег", "Slight snow fall"],
  ["Умеренный снег", "Moderate snow fall"],
  ["Сильный снег", "Heavy snow fall"],
  ["Снежные зерна", "Snow grains"],
  ["Снежные зёрна", "Snow grains"],
  ["Легкий ливень", "Slight rain showers"],
  ["Лёгкий ливень", "Slight rain showers"],
  ["Умеренный ливень", "Moderate rain showers"],
  ["Сильный ливень", "Violent rain showers"],
  ["Снегопад", "Snow showers"],
  ["Сильный снегопад", "Heavy snow showers"],
  ["Гроза", "Thunderstorm"],
  ["Гроза с градом", "Thunderstorm with hail"],
  ["Гроза с сильным градом", "Thunderstorm with heavy hail"],
  ["Неизвестно", "Unknown"],
];

const FLIGHT_TAG_PAIRS = [
  ["Прямой рейс", "Direct flight"],
  ["Самый дешевый", "Cheapest"],
  ["Самый дешёвый", "Cheapest"],
  ["Лучший вариант", "Best option"],
  ["Самый быстрый", "Fastest"],
];

const BAGGAGE_NAME_PAIRS = [
  ["Чемодан", "Suitcase"],
  ["Ручная кладь", "Carry-on"],
  ["Рюкзак", "Backpack"],
  ["Походный рюкзак", "Hiking backpack"],
  ["Сумка", "Bag"],
  ["Багаж", "Baggage"],
];

const CITY_PAIRS = [
  ["Владивосток", "Vladivostok"],
  ["Барселона", "Barcelona"],
  ["Женева", "Geneva"],
  ["Будапешт", "Budapest"],
  ["Санкт-Петербург", "Saint Petersburg"],
  ["Санкт Петербург", "Saint Petersburg"],
  ["Москва", "Moscow"],
  ["Париж", "Paris"],
  ["Лондон", "London"],
  ["Рим", "Rome"],
  ["Милан", "Milan"],
  ["Вена", "Vienna"],
  ["Прага", "Prague"],
  ["Берлин", "Berlin"],
  ["Стамбул", "Istanbul"],
  ["Токио", "Tokyo"],
  ["Сеул", "Seoul"],
  ["Пекин", "Beijing"],
  ["Шанхай", "Shanghai"],
  ["Дубай", "Dubai"],
  ["Амстердам", "Amsterdam"],
  ["Лиссабон", "Lisbon"],
  ["Мадрид", "Madrid"],
  ["Нью-Йорк", "New York"],
  ["Лос-Анджелес", "Los Angeles"],
  ["Стокгольм", "Stockholm"],
  ["Копенгаген", "Copenhagen"],
  ["Хельсинки", "Helsinki"],
  ["Варшава", "Warsaw"],
  ["Белград", "Belgrade"],
  ["Тбилиси", "Tbilisi"],
  ["Ереван", "Yerevan"],
  ["Алматы", "Almaty"],
  ["Казань", "Kazan"],
  ["Сочи", "Sochi"],
  ["Новосибирск", "Novosibirsk"],
  ["Екатеринбург", "Yekaterinburg"],
  ["Нижний Новгород", "Nizhny Novgorod"],
  ["Краснодар", "Krasnodar"],
];

const COUNTRY_PAIRS = [
  ["Россия", "Russia"],
  ["Франция", "France"],
  ["Испания", "Spain"],
  ["Швейцария", "Switzerland"],
  ["Венгрия", "Hungary"],
  ["Италия", "Italy"],
  ["Германия", "Germany"],
  ["Турция", "Turkey"],
  ["Япония", "Japan"],
  ["Китай", "China"],
  ["США", "USA"],
  ["Соединённые Штаты", "United States"],
  ["Соединенные Штаты", "United States"],
  ["Великобритания", "United Kingdom"],
  ["Нидерланды", "Netherlands"],
  ["Португалия", "Portugal"],
  ["Швеция", "Sweden"],
  ["Дания", "Denmark"],
  ["Финляндия", "Finland"],
  ["Польша", "Poland"],
  ["Сербия", "Serbia"],
  ["Грузия", "Georgia"],
  ["Армения", "Armenia"],
  ["Казахстан", "Kazakhstan"],
];

const AIRLINE_PAIRS = [
  ["Аэрофлот", "Aeroflot"],
  ["Победа", "Pobeda"],
  ["Россия", "Rossiya Airlines"],
  ["Уральские авиалинии", "Ural Airlines"],
  ["Северный ветер", "Nordwind Airlines"],
  ["Смартавиа", "Smartavia"],
  ["Ред Вингс", "Red Wings"],
  ["Якутия", "Yakutia Airlines"],
  ["Азимут", "Azimuth Airlines"],
  ["Ютэйр", "UTair"],
];

const CHECKLIST_ITEM_PAIRS = [
  ["Паспорт", "Passport"],
  ["Медицинская страховка", "Health Insurance"],
  ["Деньги/карта", "Cash/Credit Cards"],
  ["Билеты", "Tickets"],
  ["Бронь отеля", "Hotel Booking"],
  ["Водительское удостоверение/СТС", "Driver's License"],
  ["Виза", "Visa"],
  ["Копии документов (электронные)", "Document copies (digital)"],
  ["Нижнее белье", "Underwear"],
  ["Нижнее бельё", "Underwear"],
  ["Носки", "Socks"],
  ["Пижама/одежда для сна", "Pajamas/Sleepwear"],
  ["Полотенце", "Towel"],
  ["Теплая куртка", "Warm Jacket"],
  ["Тёплая куртка", "Warm Jacket"],
  ["Легкая куртка", "Light Jacket"],
  ["Лёгкая куртка", "Light Jacket"],
  ["Дождевик", "Raincoat"],
  ["Термобелье", "Thermal Underwear"],
  ["Термобельё", "Thermal Underwear"],
  ["Шапка", "Hat"],
  ["Шарф", "Scarf"],
  ["Перчатки", "Gloves"],
  ["Зимние ботинки", "Winter Boots"],
  ["Свитер", "Sweater"],
  ["Джинсы/брюки", "Jeans/Trousers"],
  ["Кроссовки", "Sneakers"],
  ["Футболки", "T-shirts"],
  ["Шорты", "Shorts"],
  ["Панама/кепка", "Cap/Hat"],
  ["Солнцезащитные очки", "Sunglasses"],
  ["Легкая обувь", "Light Shoes"],
  ["Лёгкая обувь", "Light Shoes"],
  ["Водонепроницаемая обувь", "Waterproof Shoes"],
  ["Купальник/плавки", "Swimsuit"],
  ["Худи/толстовка", "Hoodie"],
  ["Рубашка с длинным рукавом", "Long-sleeve Shirt"],
  ["Зубная щетка и паста", "Toothbrush & Paste"],
  ["Зубная щётка и паста", "Toothbrush & Paste"],
  ["Дезодорант", "Deodorant"],
  ["Мыло/гель для душа", "Soap/Shower Gel"],
  ["Шампунь", "Shampoo"],
  ["Расческа", "Hairbrush"],
  ["Расчёска", "Hairbrush"],
  ["Бритвенный набор", "Shaving Kit"],
  ["Косметика/макияж", "Makeup"],
  ["Средство для снятия макияжа", "Makeup Remover"],
  ["Влажные салфетки", "Wet Wipes"],
  ["Солнцезащитный крем", "Sunscreen"],
  ["Солнцезащитный крем (SPF 50+)", "Sunscreen (SPF 50+)"],
  ["Гигиеническая помада", "Lip Balm"],
  ["Антиперспирант", "Antiperspirant"],
  ["Средство для укладки (от влажности)", "Hair Styling Product"],
  ["Крем для рук", "Hand Cream"],
  ["Сухой шампунь", "Dry Shampoo"],
  ["Маникюрный набор", "Nail Kit"],
  ["Ватные диски", "Cotton Pads"],
  ["Бумажные салфетки", "Tissues"],
  ["Антисептик для рук", "Hand Sanitizer"],
  ["Телефон", "Phone"],
  ["Зарядка", "Charger"],
  ["Power bank", "Power Bank"],
  ["Переходник для розеток", "Power Adapter"],
  ["Наушники", "Headphones"],
  ["Ноутбук", "Laptop"],
  ["Кабель USB-C/Lightning", "USB-C/Lightning Cable"],
  ["Фотоаппарат", "Camera"],
  ["Фонарик", "Flashlight"],
  ["Личные лекарства", "Personal Meds"],
  ["Обезболивающее", "Painkillers"],
  ["Пластыри", "Plasters"],
  ["Антигистаминные", "Antihistamines"],
  ["Медзаключение", "Medical Report"],
  ["Список аллергенов", "Allergies List"],
  ["Активированный уголь/сорбенты", "Activated Charcoal"],
  ["Антисептик (для ран)", "Wound Antiseptic"],
  ["Средство от укачивания", "Motion Sickness Remedy"],
  ["Средство от насекомых (репеллент)", "Insect Repellent"],
  ["Крем после укусов", "After-Bite Cream"],
  ["Средство от диареи", "Anti-diarrhea Meds"],
  ["Леденцы для горла", "Throat Pastilles"],
  ["Бутылка для воды", "Water Bottle"],
  ["Рюкзак/Сумка", "Backpack/Bag"],
  ["Маска/антисептик", "Mask/Sanitizer"],
  ["Зонт", "Umbrella"],
  ["Термос", "Thermos"],
  ["Снеки", "Snacks"],
  ["Путеводитель/карта", "Guidebook/Map"],
  ["Органайзеры для чемодана", "Packing Cubes"],
  ["Мешок для грязного белья", "Laundry Bag"],
  ["Замок для чемодана", "Luggage Lock"],
  ["Маска для сна", "Sleep Mask"],
  ["Подушка для шеи", "Neck Pillow"],
  ["Беруши", "Earplugs"],
  ["Жидкости <100мл (в прозрачном пакете)", "Liquids <100ml bag"],
  ["Тапочки для поезда", "Train Slippers"],
  ["Кружка", "Mug"],
  ["Удобная одежда", "Comfy Clothes"],
  ["Автомобильная зарядка", "Car Charger"],
  ["Ветпаспорт", "Pet Passport"],
  ["Корм для питомца", "Pet Food"],
  ["Миска", "Pet Bowl"],
  ["Поводок/переноска", "Leash/Carrier"],
  ["Пеленки/пакеты", "Pet Pads/Bags"],
  ["Пелёнки/пакеты", "Pet Pads/Bags"],
  ["Игрушка для питомца", "Pet Toy"],
  ["Платье/юбка", "Dress/Skirt"],
  ["Костюм/деловой стиль", "Suit/Formal Wear"],
  ["Треккинговая обувь", "Trekking Shoes"],
  ["Горнолыжный костюм", "Ski Suit"],
  ["Флисовая кофта", "Fleece Jacket"],
  ["Маска/очки для снега", "Ski Goggles"],
  ["Крем от ветра/мороза", "Wind/Frost Cream"],
  ["Пляжное полотенце", "Beach Towel"],
  ["Крем после загара", "After-Sun Cream"],
  ["Сумка для пляжа", "Beach Bag"],
  ["Детское питание", "Baby Food"],
  ["Памперсы/подгузники", "Diapers"],
  ["Детские влажные салфетки", "Baby Wipes"],
  ["Коляска (складная)", "Stroller (foldable)"],
  ["Игрушки/раскраски для ребенка", "Kids Toys/Coloring Books"],
  ["Игрушки/раскраски для ребёнка", "Kids Toys/Coloring Books"],
  ["Сменная одежда для ребенка", "Extra Kids Clothes"],
  ["Сменная одежда для ребёнка", "Extra Kids Clothes"],
  ["Детская аптечка", "Kids First Aid Kit"],
  ["Детский солнцезащитный крем", "Kids Sunscreen"],
  ["Детская бутылочка/поильник", "Sippy Cup/Bottle"],
  ["Нарядная одежда (для ужина)", "Fancy Outfit (dinner)"],
  ["Парфюм/духи", "Perfume/Cologne"],
  ["Туфли на каблуке", "Heels"],
  ["Украшения", "Jewelry"],
  ["Палатка", "Tent"],
  ["Спальный мешок", "Sleeping Bag"],
  ["Каримат/надувной коврик", "Sleeping Pad"],
  ["Горелка/газ", "Camp Stove"],
  ["Посуда для кемпинга", "Camping Cookware"],
  ["Мультитул/нож", "Multitool/Knife"],
  ["Спички/зажигалка", "Matches/Lighter"],
  ["Налобный фонарик", "Headlamp"],
  ["Москитная сетка", "Bug Net"],
  ["Мусорные пакеты", "Trash Bags"],
  ["Веревка/паракорд", "Rope/Paracord"],
  ["Верёвка/паракорд", "Rope/Paracord"],
  ["Гермомешок", "Dry Bag"],
  ["Удобная обувь для ходьбы", "Comfortable Walking Shoes"],
  ["Городской рюкзак", "City Daypack"],
  ["Портативная зарядка", "Portable Charger"],
  ["Легкая куртка-дождевик", "Light Rain Jacket"],
  ["Лёгкая куртка-дождевик", "Light Rain Jacket"],
  ["Закрытая одежда (для храмов/мечетей)", "Modest Clothing (temples/mosques)"],
  ["Головной убор (для храмов)", "Head Covering (temples)"],
  ["Конвертер напряжения (110В)", "Voltage Converter (110V)"],
  ["Разговорник", "Phrasebook"],
  ["Дорожная подушка", "Travel Pillow"],
  ["Ветровка", "Windbreaker"],
  ["Шарф/бафф", "Scarf/Buff"],
  ["Аптечка", "First Aid Kit"],
  ["Карта/компас", "Map/Compass"],
  ["Запас регулярных лекарств", "Regular Medication"],
  ["Средства гигиены (женские)", "Feminine Hygiene"],
  ["Удобная одежда для поезда", "Comfy Train Clothes"],
  ["Снеки и вода", "Snacks & Water"],
  ["Плейлист/аудиокниги", "Playlist/Audiobooks"],
  ["Солнцезащитные очки (для водителя)", "Sunglasses (Driver)"],
  ["Теплые носки", "Warm Socks"],
  ["Тёплые носки", "Warm Socks"],
  ["Рубашки/блузки", "Shirts/Blouses"],
  ["Туфли/строгая обувь", "Formal Shoes"],
  ["Визитки", "Business Cards"],
  ["Спортивная одежда", "Sportswear"],
  ["Рюкзак для прогулок", "Daypack"],
  ["Пляжная туника/парео", "Beach Tunic/Pareo"],
  ["Шлепанцы", "Flip-flops"],
  ["Шлёпанцы", "Flip-flops"],
  ["Перчатки/варежки", "Gloves/Mittens"],
];

const categoryLookup = buildLookup(CATEGORY_PAIRS);
const weatherLookup = buildLookup(WEATHER_CONDITION_PAIRS);
const flightTagLookup = buildLookup(FLIGHT_TAG_PAIRS);
const baggageNameLookup = buildLookup(BAGGAGE_NAME_PAIRS);
const checklistItemLookup = buildLookup(CHECKLIST_ITEM_PAIRS);
const cityLookup = buildLookup(CITY_PAIRS);
const countryLookup = buildLookup(COUNTRY_PAIRS);
const airlineLookup = buildLookup(AIRLINE_PAIRS);

const CYRILLIC_TO_LATIN = {
  А: "A", а: "a", Б: "B", б: "b", В: "V", в: "v", Г: "G", г: "g", Д: "D", д: "d",
  Е: "E", е: "e", Ё: "Yo", ё: "yo", Ж: "Zh", ж: "zh", З: "Z", з: "z", И: "I", и: "i",
  Й: "Y", й: "y", К: "K", к: "k", Л: "L", л: "l", М: "M", м: "m", Н: "N", н: "n",
  О: "O", о: "o", П: "P", п: "p", Р: "R", р: "r", С: "S", с: "s", Т: "T", т: "t",
  У: "U", у: "u", Ф: "F", ф: "f", Х: "Kh", х: "kh", Ц: "Ts", ц: "ts", Ч: "Ch", ч: "ch",
  Ш: "Sh", ш: "sh", Щ: "Shch", щ: "shch", Ъ: "", ъ: "", Ы: "Y", ы: "y", Ь: "", ь: "",
  Э: "E", э: "e", Ю: "Yu", ю: "yu", Я: "Ya", я: "ya",
};

const transliterateCyrillic = (value = "") =>
  Array.from(String(value || "")).map((char) => CYRILLIC_TO_LATIN[char] ?? char).join("");

const containsCyrillic = (value = "") => /[А-Яа-яЁё]/.test(String(value || ""));
const containsLatin = (value = "") => /[A-Za-z]/.test(String(value || ""));
const normalizeTranslationText = (value = "") => String(value || "").trim();

export const detectItemTextLanguage = (value = "") => {
  if (containsCyrillic(value)) return "ru";
  if (containsLatin(value)) return "en";
  return "ru";
};

export const normalizeChecklistItemTranslations = (value = {}) => {
  const normalized = {};
  Object.entries(value || {}).forEach(([rawLabel, rawEntry]) => {
    const label = String(rawLabel || "").trim();
    if (!label || !rawEntry || typeof rawEntry !== "object") return;
    const ru = normalizeTranslationText(rawEntry.ru);
    const en = normalizeTranslationText(rawEntry.en);
    if (!ru && !en) return;
    normalized[label] = {};
    if (ru) normalized[label].ru = ru;
    if (en) normalized[label].en = en;
  });
  return normalized;
};

export const buildChecklistItemTranslationEntry = (
  label,
  translatedText,
  targetLang = "en",
  sourceLang = "auto"
) => {
  const original = String(label || "").trim();
  const translated = String(translatedText || "").trim();
  const safeTargetLang = targetLang === "en" ? "en" : "ru";
  const safeSourceLang = sourceLang === "auto"
    ? detectItemTextLanguage(original)
    : (sourceLang === "en" ? "en" : "ru");

  if (!original || !translated) return null;

  if (safeSourceLang === "ru") {
    return {
      ru: original,
      en: safeTargetLang === "en" ? translated : original,
    };
  }

  return {
    en: original,
    ru: safeTargetLang === "ru" ? translated : original,
  };
};

export const getChecklistItemServerTranslation = (label, lang = "ru", itemTranslations = {}) => {
  const original = String(label || "").trim();
  if (!original) return "";

  const normalizedMap = normalizeChecklistItemTranslations(itemTranslations);
  const directEntry = normalizedMap[original];
  if (directEntry?.[lang]) return directEntry[lang];

  const normalizedLabel = normalizeLookupKey(original);
  const matchedEntry = Object.entries(normalizedMap).find(
    ([entryLabel]) => normalizeLookupKey(entryLabel) === normalizedLabel
  )?.[1];
  return matchedEntry?.[lang] || "";
};

const buildItemTranslationCacheKey = (label, targetLang) =>
  `${normalizeLookupKey(label)}::${targetLang}`;

export const getCachedChecklistItemTranslation = (label, lang = "ru") => {
  const safeLang = lang === "en" ? "en" : "ru";
  const cache = readItemTranslationCache();
  return cache.get(buildItemTranslationCacheKey(label, safeLang))?.translated_text || "";
};

export const cacheChecklistItemTranslation = ({ label, translatedText, targetLang, sourceLang = "auto" }) => {
  const original = String(label || "").trim();
  const translated = String(translatedText || "").trim();
  const safeTargetLang = targetLang === "en" ? "en" : "ru";
  if (!original || !translated) return;
  const cache = readItemTranslationCache();
  cache.set(buildItemTranslationCacheKey(original, safeTargetLang), {
    source_lang: sourceLang,
    target_lang: safeTargetLang,
    translated_text: translated,
  });
  writeItemTranslationCache();
};

export const requestChecklistItemTranslation = async (label, targetLang = "en") => {
  const original = String(label || "").trim();
  const safeTargetLang = targetLang === "en" ? "en" : "ru";
  if (!original) return "";

  const cached = getCachedChecklistItemTranslation(original, safeTargetLang);
  if (cached) return cached;

  const sourceLang = detectItemTextLanguage(original);
  if (sourceLang === safeTargetLang) {
    cacheChecklistItemTranslation({ label: original, translatedText: original, targetLang: safeTargetLang, sourceLang });
    return original;
  }

  try {
    const response = await fetch(`${API_URL}/translate-item-label`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: original,
        source_lang: sourceLang,
        target_lang: safeTargetLang,
      }),
    });
    if (!response.ok) return "";
    const payload = await response.json();
    const translated = String(payload?.translated_text || "").trim();
    if (!translated) return "";
    cacheChecklistItemTranslation({
      label: original,
      translatedText: translated,
      targetLang: safeTargetLang,
      sourceLang,
    });
    return translated;
  } catch {
    return "";
  }
};

const translatePlaceToken = (token, lang = "ru") => {
  const trimmed = String(token || "").trim();
  if (!trimmed || lang !== "en") return trimmed;

  const translatedCity = translateKnownValue(trimmed, lang, cityLookup);
  if (translatedCity !== trimmed) return translatedCity;

  const translatedCountry = translateKnownValue(trimmed, lang, countryLookup);
  if (translatedCountry !== trimmed) return translatedCountry;

  return containsCyrillic(trimmed) ? transliterateCyrillic(trimmed) : trimmed;
};

export const translateChecklistCategoryLabel = (label, lang = "ru") =>
  translateKnownValue(label, lang, categoryLookup);

export const translateWeatherConditionLabel = (label, lang = "ru") =>
  translateKnownValue(label, lang, weatherLookup);

export const translateFlightTagLabel = (label, lang = "ru") =>
  translateKnownValue(label, lang, flightTagLookup);

export const translateKnownBaggageName = (label, lang = "ru") =>
  translateKnownValue(label, lang, baggageNameLookup);

export const translateChecklistItemLabel = (label, lang = "ru", itemTranslations = {}) =>
  translateKnownValue(label, lang, checklistItemLookup) !== String(label || "").trim()
    ? translateKnownValue(label, lang, checklistItemLookup)
    : (getChecklistItemServerTranslation(label, lang, itemTranslations) ||
      getCachedChecklistItemTranslation(label, lang) ||
      String(label || "").trim());

export const translateAirlineLabel = (label, lang = "ru") =>
  translateKnownValue(label, lang, airlineLookup);

export const translatePlaceLabel = (label, lang = "ru") => {
  const original = String(label || "").trim();
  if (!original || lang !== "en") return original;

  return original
    .split(/\s*\+\s*/g)
    .map((segment) => (
      segment
        .split(/\s*,\s*/g)
        .map((token) => translatePlaceToken(token, lang))
        .join(", ")
    ))
    .join(" + ");
};
