
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
    "copies_docs": {"ru": "Копии документов (электронные)", "en": "Document copies (digital)"},
    
    # Base clothing (always)
    "underwear": {"ru": "Нижнее бельё", "en": "Underwear"},
    "socks": {"ru": "Носки", "en": "Socks"},
    "pajamas": {"ru": "Пижама/одежда для сна", "en": "Pajamas/Sleepwear"},
    "towel": {"ru": "Полотенце", "en": "Towel"},
    
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
    "jeans": {"ru": "Джинсы/брюки", "en": "Jeans/Trousers"},
    "sneakers": {"ru": "Кроссовки", "en": "Sneakers"},
    "tshirt": {"ru": "Футболки", "en": "T-shirts"},
    "shorts": {"ru": "Шорты", "en": "Shorts"},
    "cap": {"ru": "Панама/кепка", "en": "Cap/Hat"},
    "sunglasses": {"ru": "Солнцезащитные очки", "en": "Sunglasses"},
    "shoes_light": {"ru": "Лёгкая обувь", "en": "Light Shoes"},
    "shoes_waterproof": {"ru": "Водонепроницаемая обувь", "en": "Waterproof Shoes"},
    "swimsuit": {"ru": "Купальник/плавки", "en": "Swimsuit"},
    "hoodie": {"ru": "Худи/толстовка", "en": "Hoodie"},
    "long_sleeve": {"ru": "Рубашка с длинным рукавом", "en": "Long-sleeve Shirt"},
    
    # Hygiene
    "toothbrush": {"ru": "Зубная щётка и паста", "en": "Toothbrush & Paste"},
    "deodorant": {"ru": "Дезодорант", "en": "Deodorant"},
    "soap": {"ru": "Мыло/гель для душа", "en": "Soap/Shower Gel"},
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
    "hand_cream": {"ru": "Крем для рук", "en": "Hand Cream"},
    "dry_shampoo": {"ru": "Сухой шампунь", "en": "Dry Shampoo"},
    "nail_kit": {"ru": "Маникюрный набор", "en": "Nail Kit"},
    "cotton_pads": {"ru": "Ватные диски", "en": "Cotton Pads"},
    "tissues": {"ru": "Бумажные салфетки", "en": "Tissues"},
    "sanitizer": {"ru": "Антисептик для рук", "en": "Hand Sanitizer"},
    
    # Tech
    "phone": {"ru": "Телефон", "en": "Phone"},
    "charger": {"ru": "Зарядка", "en": "Charger"},
    "powerbank": {"ru": "Power bank", "en": "Power Bank"},
    "adapter": {"ru": "Переходник для розеток", "en": "Power Adapter"},
    "headphones": {"ru": "Наушники", "en": "Headphones"},
    "laptop": {"ru": "Ноутбук", "en": "Laptop"},
    "usb_cable": {"ru": "Кабель USB-C/Lightning", "en": "USB-C/Lightning Cable"},
    "camera": {"ru": "Фотоаппарат", "en": "Camera"},
    "flashlight": {"ru": "Фонарик", "en": "Flashlight"},
    
    # Pharmacy
    "meds_personal": {"ru": "Личные лекарства", "en": "Personal Meds"},
    "painkillers": {"ru": "Обезболивающее", "en": "Painkillers"},
    "plasters": {"ru": "Пластыри", "en": "Plasters"},
    "antihistamine": {"ru": "Антигистаминные", "en": "Antihistamines"},
    "med_report": {"ru": "Медзаключение", "en": "Medical Report"},
    "allergies_list": {"ru": "Список аллергенов", "en": "Allergies List"},
    "activated_charcoal": {"ru": "Активированный уголь/сорбенты", "en": "Activated Charcoal"},
    "antiseptic": {"ru": "Антисептик (для ран)", "en": "Wound Antiseptic"},
    "motion_sickness": {"ru": "Средство от укачивания", "en": "Motion Sickness Remedy"},
    "insect_spray": {"ru": "Средство от насекомых (репеллент)", "en": "Insect Repellent"},
    "bite_cream": {"ru": "Крем после укусов", "en": "After-Bite Cream"},
    "diarrhea_meds": {"ru": "Средство от диареи", "en": "Anti-diarrhea Meds"},
    "throat_pastilles": {"ru": "Леденцы для горла", "en": "Throat Pastilles"},
    
    # Misc
    "water_bottle": {"ru": "Бутылка для воды", "en": "Water Bottle"},
    "backpack": {"ru": "Рюкзак/Сумка", "en": "Backpack/Bag"},
    "mask": {"ru": "Маска/антисептик", "en": "Mask/Sanitizer"},
    "umbrella": {"ru": "Зонт", "en": "Umbrella"},
    "thermos": {"ru": "Термос", "en": "Thermos"},
    "snacks": {"ru": "Снеки", "en": "Snacks"},
    "guidebook": {"ru": "Путеводитель/карта", "en": "Guidebook/Map"},
    "packing_cubes": {"ru": "Органайзеры для чемодана", "en": "Packing Cubes"},
    "laundry_bag": {"ru": "Мешок для грязного белья", "en": "Laundry Bag"},
    "lock": {"ru": "Замок для чемодана", "en": "Luggage Lock"},
    "eye_mask": {"ru": "Маска для сна", "en": "Sleep Mask"},
    
    # Trip Types / Transport
    "neck_pillow": {"ru": "Подушка для шеи", "en": "Neck Pillow"},
    "earplugs": {"ru": "Беруши", "en": "Earplugs"},
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

    # Special: Existing trip types
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

    # Special: New trip types
    # Family
    "baby_food": {"ru": "Детское питание", "en": "Baby Food"},
    "diapers": {"ru": "Памперсы/подгузники", "en": "Diapers"},
    "baby_wipes": {"ru": "Детские влажные салфетки", "en": "Baby Wipes"},
    "stroller": {"ru": "Коляска (складная)", "en": "Stroller (foldable)"},
    "kids_toys": {"ru": "Игрушки/раскраски для ребёнка", "en": "Kids Toys/Coloring Books"},
    "kids_clothes": {"ru": "Сменная одежда для ребёнка", "en": "Extra Kids Clothes"},
    "child_meds": {"ru": "Детская аптечка", "en": "Kids First Aid Kit"},
    "baby_sunscreen": {"ru": "Детский солнцезащитный крем", "en": "Kids Sunscreen"},
    "sippy_cup": {"ru": "Детская бутылочка/поильник", "en": "Sippy Cup/Bottle"},
    
    # Romantic
    "fancy_outfit": {"ru": "Нарядная одежда (для ужина)", "en": "Fancy Outfit (dinner)"},
    "perfume": {"ru": "Парфюм/духи", "en": "Perfume/Cologne"},
    "heels": {"ru": "Туфли на каблуке", "en": "Heels"},
    "jewelry": {"ru": "Украшения", "en": "Jewelry"},
    
    # Camping
    "tent": {"ru": "Палатка", "en": "Tent"},
    "sleeping_bag": {"ru": "Спальный мешок", "en": "Sleeping Bag"},
    "sleeping_pad": {"ru": "Каримат/надувной коврик", "en": "Sleeping Pad"},
    "camp_stove": {"ru": "Горелка/газ", "en": "Camp Stove"},
    "camping_cookware": {"ru": "Посуда для кемпинга", "en": "Camping Cookware"},
    "multitool": {"ru": "Мультитул/нож", "en": "Multitool/Knife"},
    "matches": {"ru": "Спички/зажигалка", "en": "Matches/Lighter"},
    "headlamp": {"ru": "Налобный фонарик", "en": "Headlamp"},
    "bug_net": {"ru": "Москитная сетка", "en": "Bug Net"},
    "trash_bags": {"ru": "Мусорные пакеты", "en": "Trash Bags"},
    "rope": {"ru": "Верёвка/паракорд", "en": "Rope/Paracord"},
    "dry_bag": {"ru": "Гермомешок", "en": "Dry Bag"},
    
    # City Break
    "comfy_shoes": {"ru": "Удобная обувь для ходьбы", "en": "Comfortable Walking Shoes"},
    "city_backpack": {"ru": "Городской рюкзак", "en": "City Daypack"},
    "portable_charger": {"ru": "Портативная зарядка", "en": "Portable Charger"},
    "rain_jacket": {"ru": "Лёгкая куртка-дождевик", "en": "Light Rain Jacket"},
    
    # Regional
    "closed_clothing": {"ru": "Закрытая одежда (для храмов/мечетей)", "en": "Modest Clothing (temples/mosques)"},
    "head_covering": {"ru": "Головной убор (для храмов)", "en": "Head Covering (temples)"},
    "converter_110v": {"ru": "Конвертер напряжения (110В)", "en": "Voltage Converter (110V)"},
    "phrasebook": {"ru": "Разговорник", "en": "Phrasebook"},
    "travel_pillow": {"ru": "Дорожная подушка", "en": "Travel Pillow"},

    # Aliases for backward compatibility
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
    if lang == "en":
        return {
            "Essentials": ["Passport", "Insurance", "Money", "Card", "Visa", "Ticket", "Booking", "License", "Document"],
            "Documents": ["List", "Report", "Receipt", "Prescription", "Phrasebook"],
            "Clothes": ["Jacket", "T-shirt", "Jeans", "Shorts", "Sweater", "Coat", "Dress", "Skirt", "Underwear", "Socks", "Shoes", "Boots", "Sneakers", "Hat", "Scarf", "Gloves", "Swimsuit", "Hoodie", "Long-sleeve", "Pajamas", "Sportswear", "Ski Suit", "Fleece", "Windbreaker", "Pareo", "Flip-flops", "Mittens", "Suit", "Shirts", "Blouses", "Formal", "Modest Clothing", "Head Covering", "Fancy Outfit", "Heels", "Jewelry", "Walking Shoes", "Towel"],
            "Hygiene": ["Toothbrush", "Paste", "Deodorant", "Soap", "Shampoo", "Brush", "Comb", "Makeup", "Wipes", "Shaving", "Cream", "Sunscreen", "Balm", "Sanitizer", "Cotton", "Tissues", "Nail", "Perfume"],
            "Electronics": ["Phone", "Charger", "Power", "Adapter", "Laptop", "Headphones", "USB", "Camera", "Flashlight", "Headlamp", "Converter"],
            "Pharmacy": ["Meds", "Pills", "Painkiller", "Plaster", "Antihistamine", "Charcoal", "Antiseptic", "Motion Sickness", "Repellent", "Bite", "Diarrhea", "Throat", "First Aid"],
            "Kids": ["Baby", "Diaper", "Stroller", "Kids", "Sippy", "Child"],
            "Camping": ["Tent", "Sleeping", "Camp", "Cookware", "Multitool", "Matches", "Bug Net", "Trash Bag", "Rope", "Dry Bag"],
            "Misc": ["Bottle", "Bag", "Backpack", "Mask", "Umbrella", "Snacks", "Pillow", "Earplugs", "Mug", "Pet", "Leash", "Toy", "Lock", "Guidebook", "Packing Cubes", "Laundry", "Sleep Mask", "Thermos", "Map", "Compass", "Playlist"]
        }
    else:
        return {
            "Важное": ["Паспорт", "Медицинская страховка", "Деньги/карта", "Виза", "Билеты", "Бронь отеля", "Водительское удостоверение/СТС", "Ветпаспорт", "Копии документов"],
            "Документы": ["Список аллергенов", "Медзаключение", "Личные рецепты", "Разговорник"],
            "Одежда": ["куртка", "пуховик", "Термобельё", "Шапка", "Шарф", "Перчатки", "ботинки", "носки", "Свитер", "толстовка", "Джинсы", "брюки", "Кроссовки", "кофта", "свитшот", "Футболки", "Шорты", "платья", "Панама", "кепка", "очки", "Обувь", "Дождевик", "Купальник", "плавки", "туника", "парео", "Шлёпанцы", "Костюм", "Рубашки", "блузки", "Туфли", "юбка", "Худи", "Пижама", "бельё", "Ветровка", "Спортивная одежда", "Горнолыжный", "Флисовая", "Закрытая одежда", "Головной убор", "Нарядная одежда", "каблуке", "Украшения", "варежки", "Полотенце"],
            "Гигиена": ["Зубная", "Паста", "Дезодорант", "Мыло", "Расчёска", "Косметика", "макияж", "Влажные салфетки", "Бритвенный набор", "Антиперспирант", "Шампунь", "Крем для рук", "Сухой шампунь", "Маникюрный", "Ватные", "Бумажные салфетки", "Антисептик для рук", "Средство для снятия", "Парфюм", "духи"],
            "Техника": ["Телефон", "Зарядка", "Пауэрбанк", "Power bank", "Переходник", "Ноутбук", "Наушники", "Кабель USB", "Фотоаппарат", "Фонарик", "Налобный", "Конвертер", "Портативная зарядка"],
            "Аптечка": ["лекарства", "Пластыри", "Обезболивающее", "Антигистаминные", "Аптечка", "уголь", "сорбент", "ран", "укачивания", "репеллент", "насекомых", "укусов", "диареи", "горла", "Детская аптечка"],
            "Для детей": ["Детское питание", "Памперсы", "подгузник", "Детские влажные", "Коляска", "Игрушки", "раскраски", "Сменная одежда для ребёнка", "Детский солнцезащитный", "Детская бутылочка", "поильник"],
            "Кемпинг": ["Палатка", "Спальный мешок", "Каримат", "надувной коврик", "Горелка", "газ", "Посуда для кемпинга", "Мультитул", "нож", "Спички", "зажигалка", "Москитная сетка", "Мусорные пакеты", "Верёвка", "паракорд", "Гермомешок"],
            "Прочее": ["Бутылка", "Термос", "рюкзак", "Сумка", "Крем", "Снеки", "Плейлист", "Подушка", "Беруши", "маска", "Жидкости", "Тапочки", "Кружка", "Миска", "Поводок", "переноска", "Пелёнки", "пакеты", "Игрушка", "Визитки", "Зонт", "Замок для чемодана", "Путеводитель", "Органайзеры", "Мешок для грязного", "Маска для сна", "Карта", "компас"]
        }

