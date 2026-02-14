
# Weather conditions mapping
WMO_CODES = {
    "ru": {
        0: ("Ясно", "01d"), 1: ("Преимущественно ясно", "02d"), 2: ("Переменная облачность", "03d"), 3: ("Пасмурно", "04d"),
        45: ("Туман", "50d"), 48: ("Изморозь", "50d"), 51: ("Лёгкая морось", "09d"), 53: ("Умеренная морось", "09d"), 55: ("Сильная морось", "09d"),
        61: ("Небольшой дождь", "10d"), 63: ("Умеренный дождь", "10d"), 65: ("Сильный дождь", "10d"), 66: ("Ледяной дождь", "13d"),
        67: ("Сильный ледяной дождь", "13d"), 71: ("Небольшой снег", "13d"), 73: ("Умеренный снег", "13d"), 75: ("Сильный снег", "13d"),
        77: ("Снежные зёрна", "13d"), 80: ("Лёгкий ливень", "09d"), 81: ("Умеренный ливень", "09d"), 82: ("Сильный ливень", "09d"),
        85: ("Снегопад", "13d"), 86: ("Сильный снегопад", "13d"), 95: ("Гроза", "11d"), 96: ("Гроза с градом", "11d"), 99: ("Гроза с сильным градом", "11d"),
    },
    "en": {
        0: ("Clear sky", "01d"), 1: ("Mainly clear", "02d"), 2: ("Partly cloudy", "03d"), 3: ("Overcast", "04d"),
        45: ("Fog", "50d"), 48: ("Depositing rime fog", "50d"), 51: ("Light drizzle", "09d"), 53: ("Moderate drizzle", "09d"), 55: ("Dense drizzle", "09d"),
        61: ("Slight rain", "10d"), 63: ("Moderate rain", "10d"), 65: ("Heavy rain", "10d"), 66: ("Freezing rain", "13d"),
        67: ("Heavy freezing rain", "13d"), 71: ("Slight snow fall", "13d"), 73: ("Moderate snow fall", "13d"), 75: ("Heavy snow fall", "13d"),
        77: ("Snow grains", "13d"), 80: ("Slight rain showers", "09d"), 81: ("Moderate rain showers", "09d"), 82: ("Violent rain showers", "09d"),
        85: ("Snow showers", "13d"), 86: ("Heavy snow showers", "13d"), 95: ("Thunderstorm", "11d"), 96: ("Thunderstorm with hail", "11d"), 99: ("Thunderstorm with heavy hail", "11d"),
    }
}

# Categories
CATEGORIES = {
    "ru": ["Важное", "Документы", "Одежда", "Гигиена", "Техника", "Аптечка", "Прочее"],
    "en": ["Essentials", "Documents", "Clothes", "Hygiene", "Electronics", "Pharmacy", "Misc"]
}

# Items database (key -> {lang: translation})
# Using keys allows better scaling, but for simplicity we can use reverse mapping or just direct dictionaries per lang.
# Let's use direct dictionaries for items to keep generate_list logic readable.

ITEMS_DB = {
    # Essentials
    "passport": {"ru": "Паспорт", "en": "Passport"},
    "insurance": {"ru": "Медицинская страховка", "en": "Health Insurance"},
    "money": {"ru": "Деньги/карта", "en": "Cash/Credit Cards"},
    "tickets": {"ru": "Билеты", "en": "Tickets"},
    "booking": {"ru": "Бронь отеля", "en": "Hotel Booking"},
    "license": {"ru": "Водительское удостоверение/СТС", "en": "Driver's License"},
    "visa": {"ru": "Виза", "en": "Visa"},
    
    # Clothes (Weather based)
    "jacket_warm": {"ru": "Тёплая куртка", "en": "Warm Jacket"},
    "jacket_light": {"ru": "Лёгкая куртка", "en": "Light Jacket"},
    "raincoat": {"ru": "Дождевик", "en": "Raincoat"},
    "thermo": {"ru": "Термобельё", "en": "Thermal Underwear"},
    "hat": {"ru": "Шапка", "en": "Hat"},
    "scarf": {"ru": "Шарф", "en": "Scarf"},
    "gloves": {"ru": "Перчатки", "en": "Gloves"},
    "boots_winter": {"ru": "Зимние ботинки", "en": "Winter Boots"},
    "sweater": {"ru": "Свитер", "en": "Sweater"},
    "jeans": {"ru": "Джинсы", "en": "Jeans"},
    "sneakers": {"ru": "Кроссовки", "en": "Sneakers"},
    "tshirt": {"ru": "Футболки", "en": "T-shirts"},
    "shorts": {"ru": "Шорты", "en": "Shorts"},
    "cap": {"ru": "Панама", "en": "Cap/Hat"},
    "sunglasses": {"ru": "Солнцезащитные очки", "en": "Sunglasses"},
    "shoes_light": {"ru": "Легкая обувь", "en": "Light Shoes"},
    "shoes_waterproof": {"ru": "Водонепроницаемая обувь", "en": "Waterproof Shoes"},
    "swimsuit": {"ru": "Купальник", "en": "Swimsuit"},
    
    # Hygiene
    "toothbrush": {"ru": "Збная щётка и паста", "en": "Toothbrush & Paste"},
    "deodorant": {"ru": "Дезодорант", "en": "Deodorant"},
    "soap": {"ru": "Мыло", "en": "Soap"},
    "shampoo": {"ru": "Шампунь", "en": "Shampoo"},
    "hairbrush": {"ru": "Расчёска", "en": "Hairbrush"},
    "shaving_kit": {"ru": "Бритвенный набор", "en": "Shaving Kit"},
    "makeup": {"ru": "Косметика/макияж", "en": "Makeup"},
    "makeup_remover": {"ru": "Средство для снятия макияжа", "en": "Makeup Remover"},
    "wipes": {"ru": "Влажные салфетки", "en": "Wet Wipes"},
    "sunscreen": {"ru": "Солнцезащитный крем", "en": "Sunscreen"},
    "sunscreen_50": {"ru": "Солнцезащитный крем (SPF 50+)", "en": "Sunscreen (SPF 50+)"},
    "chapstick": {"ru": "Гигиеническая помада", "en": "Lip Balm"},
    "antiperspirant": {"ru": "Антиперспирант", "en": "Antiperspirant"},
    "styling_product": {"ru": "Средство для укладки (от влажности)", "en": "Hair Styling Product"},
    
    # Tech
    "phone": {"ru": "Телефон", "en": "Phone"},
    "charger": {"ru": "Зарядка", "en": "Charger"},
    "powerbank": {"ru": "Power bank", "en": "Power Bank"},
    "adapter": {"ru": "Переходник для розеток", "en": "Power Adapter"},
    "headphones": {"ru": "Наушники", "en": "Headphones"},
    "laptop": {"ru": "Ноутбук", "en": "Laptop"},
    
    # Pharmacy
    "meds_personal": {"ru": "Личные лекарства", "en": "Personal Meds"},
    "painkillers": {"ru": "Обезболивающее", "en": "Painkillers"},
    "plasters": {"ru": "Пластыри", "en": "Plasters"},
    "antihistamine": {"ru": "Антигистаминные", "en": "Antihistamines"},
    "med_report": {"ru": "Медзаключение", "en": "Medical Report"},
    "allergies_list": {"ru": "Список аллергенов", "en": "Allergies List"},
    
    # Misc
    "water_bottle": {"ru": "Бутылка для воды", "en": "Water Bottle"},
    "backpack": {"ru": "Рюкзак/Сумка", "en": "Backpack/Bag"},
    "mask": {"ru": "Маска/антисептик", "en": "Mask/Sanitizer"},
    "umbrella": {"ru": "Зонт", "en": "Umbrella"},
    "thermos": {"ru": "Термос", "en": "Thermos"},
    "snacks": {"ru": "Снеки", "en": "Snacks"},
    
    # Trip Types / Transport
    "neck_pillow": {"ru": "Подушка для шеи", "en": "Neck Pillow"},
    "earplugs": {"ru": "Беруши/маска для сна", "en": "Earplugs/Sleep Mask"},
    "liquids_bag": {"ru": "Жидкости <100мл (в прозрачном пакете)", "en": "Liquids <100ml bag"},
    "slippers_train": {"ru": "Тапочки для поезда", "en": "Train Slippers"},
    "mug": {"ru": "Кружка", "en": "Mug"},
    "clothes_comfy": {"ru": "Удобная одежда", "en": "Comfy Clothes"},
    "car_charger": {"ru": "Автомобильная зарядка", "en": "Car Charger"},
    
    # Pet
    "vet_passport": {"ru": "Ветпаспорт", "en": "Pet Passport"},
    "pet_food": {"ru": "Корм для питомца", "en": "Pet Food"},
    "pet_bowl": {"ru": "Миска", "en": "Pet Bowl"},
    "leash": {"ru": "Поводок/переноска", "en": "Leash/Carrier"},
    "pet_pads": {"ru": "Пелёнки/пакеты", "en": "Pet Pads/Bags"},
    "pet_toy": {"ru": "Игрушка для питомца", "en": "Pet Toy"},

    # Special
    "dress": {"ru": "Платье/юбка", "en": "Dress/Skirt"},
    "suit": {"ru": "Костюм/деловой стиль", "en": "Suit/Formal Wear"},
    "trekking_shoes": {"ru": "Треккинговая обувь", "en": "Trekking Shoes"},
    "ski_suit": {"ru": "Горнолыжный костюм", "en": "Ski Suit"},
    "fleece": {"ru": "Флисовая кофта", "en": "Fleece Jacket"},
    "goggles": {"ru": "Маска/очки для снега", "en": "Ski Goggles"},
    "wind_cream": {"ru": "Крем от ветра/мороза", "en": "Wind/Frost Cream"},
    "beach_towel": {"ru": "Пляжное полотенце", "en": "Beach Towel"},
    "after_sun": {"ru": "Крем после загара", "en": "After-Sun Cream"},
    "beach_bag": {"ru": "Сумка для пляжа", "en": "Beach Bag"},

    # Missing items
    "styling": {"ru": "Средство для укладки (от влажности)", "en": "Hair Styling Product"},
    "windbreaker": {"ru": "Ветровка", "en": "Windbreaker"},
    "scarf_buff": {"ru": "Шарф/бафф", "en": "Scarf/Buff"},
    "first_aid_kit": {"ru": "Аптечка", "en": "First Aid Kit"},
    "map_compass": {"ru": "Карта/компас", "en": "Map/Compass"},
    "meds_regular": {"ru": "Запас регулярных лекарств", "en": "Regular Medication"},
    "hygiene_fem": {"ru": "Средства гигиены (женские)", "en": "Feminine Hygiene"},
    "powerbank_hand": {"ru": "Power bank (в ручную кладь)", "en": "Power Bank (Carry-on)"},
    "clothes_train": {"ru": "Удобная одежда для поезда", "en": "Comfy Train Clothes"},
    "snacks_water": {"ru": "Снеки и вода", "en": "Snacks & Water"},
    "playlist": {"ru": "Плейлист/аудиокниги", "en": "Playlist/Audiobooks"},
    "sunglasses_driver": {"ru": "Солнцезащитные очки (для водителя)", "en": "Sunglasses (Driver)"},
    "socks_warm": {"ru": "Тёплые носки", "en": "Warm Socks"},
    "shirts": {"ru": "Рубашки/блузки", "en": "Shirts/Blouses"},
    "shoes_formal": {"ru": "Туфли/строгая обувь", "en": "Formal Shoes"},
    "business_cards": {"ru": "Визитки", "en": "Business Cards"},
    "sportswear": {"ru": "Спортивная одежда", "en": "Sportswear"},
    "backpack_walk": {"ru": "Рюкзак для прогулок", "en": "Daypack"},
    "pareo": {"ru": "Пляжная туника/парео", "en": "Beach Tunic/Pareo"},
    "flipflops": {"ru": "Шлёпанцы", "en": "Flip-flops"},
    "mittens": {"ru": "Перчатки/варежки", "en": "Gloves/Mittens"},
}

def get_item(key, lang="ru"):
    return ITEMS_DB.get(key, {}).get(lang, ITEMS_DB.get(key, {}).get("ru", key))

def get_category_map(lang="ru"):
    # Dynamic mapping generation based on basic keywords isn't great for translation.
    # We should rely on explicit item keys if possible, but our current system is string-based.
    # Let's recreate the mapping with translated keywords.
    
    if lang == "en":
        return {
            "Essentials": ["Passport", "Insurance", "Money", "Card", "Visa", "Ticket", "Booking", "License"],
            "Documents": ["List", "Report", "Receipt", "Prescription"],
            "Clothes": ["Jacket", "T-shirt", "Jeans", "Shorts", "Sweater", "Coat", "Dress", "Skirt", "Underwear", "Socks", "Shoes", "Boots", "Sneakers", "Hat", "Scarf", "Gloves", "Swimsuit"],
            "Hygiene": ["Toothbrush", "Paste", "Deodorant", "Soap", "Shampoo", "Brush", "Comb", "Makeup", "Wipes", "Shaving", "Cream", "Sunscreen", "Balm"],
            "Electronics": ["Phone", "Charger", "Power", "Adapter", "Laptop", "Headphones"],
            "Pharmacy": ["Meds", "Pills", "Painkiller", "Plaster", "Antihistamine"],
            "Misc": ["Bottle", "Bag", "Backpack", "Mask", "Umbrella", "Snacks", "Pillow", "Earplugs", "Mug", "Pet", "Leash", "Toy"]
        }
    else:
        # Default RU
        return {
            "Важное": ["Паспорт", "Медицинская страховка", "Деньги/карта", "Виза", "Билеты", "Бронь отеля", "Водительское удостоверение/СТС", "Ветпаспорт"],
            "Документы": ["Список аллергенов", "Медзаключение", "Личные рецепты"],
            "Одежда": ["куртка", "пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "ботинки", "носки", "Свитер", "толстовка", "Джинсы", "брюки", "Кроссовки", "кофта", "свитшот", "Футболки", "Шорты", "платья", "Панама", "кепка", "очки", "Обувь", "Дождевик", "Зонт", "Купальник", "плавки", "туника", "парео", "Шлёпанцы", "Костюм", "Рубашки", "блузки", "Туфли", "юбка"],
            "Гигиена": ["Зубная", "Паста", "Дезодорант", "Мыло", "Расчёска", "Косметика", "макияж", "Влажные салфетки", "Бритвенный набор", "Антиперспирант", "Шампунь"],
            "Техника": ["Телефон", "Зарядка", "Пауэрбанк", "Power bank", "Переходник", "Ноутбук", "Наушники"],
            "Аптечка": ["лекарства", "Пластыри", "Обезболивающее", "Антигистаминные"],
            "Прочее": ["Бутылка", "Термос", "рюкзак", "Сумка", "Крем", "Снеки", "Плейлист", "Подушка", "Беруши", "маска", "Жидкости", "Тапочки", "Кружка", "Миска", "Поводок", "переноска", "Пелёнки", "пакеты", "Игрушка", "Визитки"]
        }
